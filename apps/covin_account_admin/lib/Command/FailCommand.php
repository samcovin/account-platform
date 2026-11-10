<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Command;

use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Db\AuditEventMapper;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

final class FailCommand extends Command {
    public function __construct(
        private AccountRequestMapper $requests,
        private AuditEventMapper $auditEvents,
    ) {
        parent::__construct();
    }

    protected function configure(): void {
        $this->setName('covin-account:fail')
            ->setDescription('Mark a claimed account request failed')
            ->addArgument('id', InputArgument::REQUIRED, 'Request ID')
            ->addArgument('claim-token', InputArgument::REQUIRED, 'Ephemeral claim token')
            ->addArgument('error', InputArgument::REQUIRED, 'Sanitized failure message');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        $id = (int)$input->getArgument('id');
        $token = (string)$input->getArgument('claim-token');
        $error = trim((string)$input->getArgument('error'));

        if ($id < 1 || !preg_match('/^[a-f0-9]{48}$/', $token)) {
            $output->writeln('<error>Invalid request ID or claim token.</error>');
            return self::INVALID;
        }

        if ($error === '') {
            $error = 'The host approval worker failed without a message.';
        }

        $error = mb_substr(preg_replace('/[\r\n]+/', ' ', $error) ?? '', 0, 4000);

        $request = $this->requests->find($id);
        $jobType = $request->getJobType();

        if (!$this->requests->fail($id, $token, $error, $jobType === 'resend')) {
            $output->writeln('<error>Request is not running or the claim token does not match.</error>');
            return self::FAILURE;
        }

        $this->auditEvents->record(
            $id,
            'host-worker',
            $jobType === 'resend' ? 'resend_failed' : 'failed',
            $error
        );
        $output->writeln(json_encode(['failed' => true, 'id' => $id], JSON_THROW_ON_ERROR));
        return self::SUCCESS;
    }
}
