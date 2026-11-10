<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Command;

use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Service\ClosureRegistry;
use OCP\IGroupManager;
use OCP\IUserManager;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/** Host-only CLI protocol. No deletion, unfreeze, reuse or mark-closed command. */
final class ClosureGuardCommand extends Command {
    public function __construct(
        private ClosureRegistry $closure,
        private AccountRequestMapper $requests,
        private IUserManager $users,
        private IGroupManager $groups,
    ) {
        parent::__construct();
    }

    protected function configure(): void {
        $this->setName('covin-account:closure-guard')
            ->setDescription('Inspect/reserve one username; never delete an account')
            ->addArgument('action', InputArgument::REQUIRED, 'inspect, freeze, begin-execution, end-execution')
            ->addArgument('username', InputArgument::REQUIRED, 'Exact canonical username')
            ->addOption('operator', null, InputOption::VALUE_REQUIRED)
            ->addOption('reason', null, InputOption::VALUE_REQUIRED)
            ->addOption('commit', null, InputOption::VALUE_NONE)
            ->addOption('confirm', null, InputOption::VALUE_REQUIRED);
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        try {
            $username = (string)$input->getArgument('username');
            $action = (string)$input->getArgument('action');
            ClosureRegistry::validateUsername($username);
            if (!in_array($action, ['inspect', 'freeze', 'begin-execution', 'end-execution'], true)) {
                throw new \InvalidArgumentException('Unknown guard action');
            }
            $row = $this->closure->read($username);
            if ($action === 'inspect' || !$input->getOption('commit')) {
                $output->writeln(json_encode([
                    'status' => 'guard-inspection', 'state' => $row['state'] ?? 'open',
                    'blocked' => $row !== null && $row['state'] !== 'open',
                    'execution_reserved' => $row !== null && $row['execution_hash'] !== '',
                    'data_deletion' => false, 'snapshot_is_atomic' => false,
                    'freeze_clearance' => false,
                ], JSON_THROW_ON_ERROR));
                return self::SUCCESS;
            }
            if ($action === 'freeze') {
                if ($input->getOption('confirm') !== 'FREEZE') {
                    throw new \RuntimeException('Exact FREEZE confirmation required');
                }
                $user = $this->users->get($username);
                if ($user === null || $user->isEnabled() || $this->groups->isAdmin($username)
                    || in_array($username, [
                        'admin', 'administrator', 'root', 'abuse', 'postmaster', 'hostmaster',
                        'webmaster', 'security', 'mailer-daemon', 'requests', 'support',
                        'billing', 'noreply', 'no-reply', 'covin-export-delivery',
                    ], true)) {
                    throw new \RuntimeException('Existing disabled non-administrator member required');
                }
                $this->requests->freezeUsername($username,
                    trim((string)$input->getOption('operator')),
                    trim((string)$input->getOption('reason')));
                $output->writeln('{"status":"username-frozen","data_deletion":false}');
            } elseif ($action === 'begin-execution') {
                // Output must go only to a root-protected temporary file, never logs.
                $output->writeln($this->closure->beginExecution($username));
            } else {
                $token = getenv('COVIN_EXECUTION_TOKEN');
                $this->closure->endExecution($username, $token === false ? '' : $token);
                $output->writeln('{"status":"execution-released","data_deletion":false}');
            }
            return self::SUCCESS;
        } catch (\Throwable $error) {
            // Do not print database errors, execution tokens or private row values.
            $output->writeln('STOP: closure guard refused or unavailable; inspect protected state before retry.');
            return self::FAILURE;
        }
    }
}
