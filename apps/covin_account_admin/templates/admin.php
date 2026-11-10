<?php
script('covin_account_admin', 'admin');
style('covin_account_admin', 'admin');
?>
<div id="covin-account-admin" class="section">
    <h2>Account approvals</h2>
    <p class="settings-hint">
        Review requests and queue approved accounts for the restricted host worker.
        External service credentials are not stored in Nextcloud.
    </p>

    <h3>Enter a request</h3>
    <form id="covin-account-form">
        <div class="covin-account-fields">
            <label>
                Display name
                <input id="covin-display-name" type="text" maxlength="100" required autocomplete="off">
            </label>
            <label>
                Username
                <input id="covin-username" type="text" minlength="2" maxlength="64" required
                       pattern="[a-z0-9][a-z0-9._-]*[a-z0-9]" autocomplete="off">
            </label>
            <label>
                Current contact email
                <input id="covin-contact-email" type="email" maxlength="254" required autocomplete="off">
            </label>
            <label>
                Enrollment link expires
                <select id="covin-invitation-days">
                    <option value="7">7 days</option>
                    <option value="14" selected>14 days</option>
                    <option value="30">30 days</option>
                </select>
            </label>
        </div>
        <p class="settings-hint covin-invitation-warning">
            Enrollment links are single-use. Opening one begins enrollment and it cannot then be
            moved to another browser or device. A replacement link invalidates any earlier link.
            Resend a link only while the person has not finished enrollment.
        </p>
        <button class="primary" type="submit">Add pending request</button>
        <p id="covin-account-message" aria-live="polite"></p>
    </form>

    <div class="covin-account-heading">
        <h3>Requests</h3>
        <button id="covin-account-refresh" type="button">Refresh</button>
    </div>

    <div class="covin-account-table-wrap">
        <form id="covin-request-filter" class="covin-request-filter">
            <label>View
                <select id="covin-request-view">
                    <option value="active">Active requests and accounts</option>
                    <option value="rejected">Archived rejections</option>
                </select>
            </label>
            <label>Search name, username, or contact email
                <input id="covin-request-search" type="search" maxlength="254" autocomplete="off">
            </label>
            <button type="submit">Search</button>
        </form>
        <p class="settings-hint">Rejected requests are automatically archived. Their reasons and history are retained for administrator review.</p>
        <table id="covin-account-requests">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Username</th>
                    <th>Contact email</th>
                    <th>Invitation</th>
                    <th>Status</th>
                    <th>Updated</th>
                    <th>Result</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <tr><td colspan="8">Loading…</td></tr>
            </tbody>
        </table>
        <div class="covin-request-pages">
            <button id="covin-request-previous" type="button" disabled>Previous</button>
            <span id="covin-request-page" aria-live="polite"></span>
            <button id="covin-request-next" type="button" disabled>Next</button>
        </div>
    </div>
</div>
