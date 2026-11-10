<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Command;

use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Db\AuditEventMapper;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

final class CompleteCommand extends Command {
    public function __construct(
        private AccountRequestMapper $requests,
        private AuditEventMapper $auditEvents,
    ) {
        parent::__construct();
    }

    protected function configure(): void {
        $this->setName('covin-account:complete')
            ->setDescription('Mark a claimed account request complete')
            ->addArgument('id', InputArgument::REQUIRED, 'Request ID')
            ->addArgument('claim-token', InputArgument::REQUIRED, 'Ephemeral claim token')
            ->addArgument('mailbox', InputArgument::REQUIRED, 'Created mailbox address');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        $id = (int)$input->getArgument('id');
        $token = (string)$input->getArgument('claim-token');
        $mailbox = mb_strtolower(trim((string)$input->getArgument('mailbox')));

        if ($id < 1 || !preg_match('/^[a-f0-9]{48}$/', $token)) {
            $output->writeln('<error>Invalid request ID or claim token.</error>');
            return self::INVALID;
        }

        if (strlen($mailbox) > 320 || filter_var($mailbox, FILTER_VALIDATE_EMAIL) === false) {
            $output->writeln('<error>Invalid mailbox address.</error>');
            return self::INVALID;
        }

        $request = $this->requests->find($id);
        $jobType = $request->getJobType();
        $invitationDays = $request->getInvitationDays();

        if (!$this->requests->complete($id, $token, $mailbox)) {
            $output->writeln('<error>Request is not running or the claim token does not match.</error>');
            return self::FAILURE;
        }

        if ($jobType === 'resend') {
            $this->auditEvents->record(
                $id,
                'host-worker',
                'resent',
                'Sent a replacement ' . $invitationDays . '-day enrollment invitation.'
            );
        } else {
            $this->auditEvents->record($id, 'host-worker', 'completed', 'Created mailbox ' . $mailbox . '.');
        }
        $output->writeln(json_encode(['completed' => true, 'id' => $id], JSON_THROW_ON_ERROR));
        return self::SUCCESS;
    }
}
