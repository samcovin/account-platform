<?php

declare(strict_types=1);

namespace OCA\CovinAccountAdmin\Command;

use OCA\CovinAccountAdmin\Db\AccountRequestMapper;
use OCA\CovinAccountAdmin\Db\AuditEventMapper;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

final class ClaimCommand extends Command {
    public function __construct(
        private AccountRequestMapper $requests,
        private AuditEventMapper $auditEvents,
    ) {
        parent::__construct();
    }

    protected function configure(): void {
        $this->setName('covin-account:claim')
            ->setDescription('Atomically claim one queued account request as JSON');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        $request = $this->requests->claimNext();

        if ($request === null) {
            $output->writeln(json_encode(['job' => null], JSON_UNESCAPED_SLASHES));
            return self::SUCCESS;
        }

        $this->auditEvents->record(
            $request->getId(),
            'host-worker',
            'claimed',
            'Claimed by the restricted host worker.'
        );

        $output->writeln(json_encode(
            ['job' => $request->toWorkerArray()],
            JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
        ));
        return self::SUCCESS;
    }
}
