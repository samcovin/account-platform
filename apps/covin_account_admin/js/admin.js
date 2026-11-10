(function () {
    'use strict';

    const root = document.getElementById('covin-account-admin');
    if (!root) return;

    const form = document.getElementById('covin-account-form');
    const displayName = document.getElementById('covin-display-name');
    const username = document.getElementById('covin-username');
    const contactEmail = document.getElementById('covin-contact-email');
    const invitationDays = document.getElementById('covin-invitation-days');
    const message = document.getElementById('covin-account-message');
    const refresh = document.getElementById('covin-account-refresh');
    const tbody = document.querySelector('#covin-account-requests tbody');
    const endpoint = OC.generateUrl('/apps/covin_account_admin/requests');
    const browserEndpoint = OC.generateUrl('/apps/covin_account_admin/request-browser');
    const filter = document.getElementById('covin-request-filter');
    const view = document.getElementById('covin-request-view');
    const search = document.getElementById('covin-request-search');
    const previous = document.getElementById('covin-request-previous');
    const next = document.getElementById('covin-request-next');
    const pageLabel = document.getElementById('covin-request-page');
    let page = 0;
    let searchTerm = '';
    let loadSequence = 0;
    let actionsInFlight = 0;

    async function request(url, options) {
        const response = await fetch(url, Object.assign({
            headers: {
                'Content-Type': 'application/json',
                'requesttoken': OC.requestToken
            }
        }, options || {}));

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error('The server returned an unreadable response.');
        }

        if (!response.ok) {
            throw new Error(data.error || 'Request failed with HTTP ' + response.status + '.');
        }

        return data;
    }

    function cellText(row, value) {
        const cell = row.insertCell();
        cell.textContent = value == null ? '' : String(value);
        return cell;
    }

    function formatDate(timestamp) {
        if (!timestamp) return '—';
        return new Date(timestamp * 1000).toLocaleString();
    }

    function actionButton(label, className, handler, refreshAfter) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        if (className) button.className = className;
        button.addEventListener('click', async function () {
            button.disabled = true;
            actionsInFlight++;
            try {
                await handler();
                if (refreshAfter !== false) {
                    await loadRequests();
                }
            } catch (error) {
                message.textContent = error.message;
            } finally {
                actionsInFlight--;
                button.disabled = false;
            }
        });
        return button;
    }

    function durationSelect(value) {
        const select = document.createElement('select');
        select.setAttribute('aria-label', 'Replacement invitation duration');

        [7, 14, 30].forEach(function (days) {
            const option = document.createElement('option');
            option.value = String(days);
            option.textContent = days + ' days';
            option.selected = Number(value) === days;
            select.appendChild(option);
        });

        return select;
    }

    function historyDetails(item) {
        const details = document.createElement('details');
        details.className = 'covin-history';

        const summary = document.createElement('summary');
        summary.textContent = 'History';
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = 'covin-history-content';
        details.appendChild(content);

        let loaded = false;
        let historyPage = 0;
        let busy = false;
        const more = actionButton('Older history', '', async function () { await loadHistory(); }, false);
        more.hidden = true;
        details.appendChild(more);
        async function loadHistory() {
            if (busy) return;
            busy = true;
            if (!loaded) content.textContent = 'Loading history…';
            try {
                const events = await request(endpoint + '/' + item.id + '/audit?page=' + historyPage);
                if (!loaded) content.replaceChildren();
                more.hidden = events.length < 100;

                if (!events.length) {
                    if (!loaded) content.textContent = 'No audit events.';
                    loaded = true;
                    return;
                }

                const list = document.createElement('ul');
                events.forEach(function (event) {
                    const entry = document.createElement('li');
                    entry.textContent = formatDate(event.createdAt) + ' — ' + event.action +
                        ' by ' + event.actor + (event.details ? ': ' + event.details : '');
                    list.appendChild(entry);
                });
                content.appendChild(list);
                historyPage++;
                loaded = true;
            } catch (error) {
                message.textContent = error.message;
                if (!loaded) content.textContent = 'Unable to load history. Close and reopen to retry.';
            } finally {
                busy = false;
            }
        }
        details.addEventListener('toggle', function () {
            if (details.open && !loaded) loadHistory();
        });

        return details;
    }

    function renderRequest(item) {
        const row = tbody.insertRow();
        row.className = 'covin-request-row';
        cellText(row, item.displayName);
        cellText(row, item.username);
        cellText(row, item.contactEmail);
        cellText(row, item.invitationDays + ' days');

        const statusCell = cellText(row, item.status);
        statusCell.className = 'covin-status covin-status-' + item.status;
        cellText(row, formatDate(item.updatedAt));
        cellText(row, item.errorMessage || item.mailbox || '—');

        const actions = row.insertCell();
        actions.className = 'covin-account-actions';

        const closureBlocked = item.closureState && item.closureState !== 'open';
        if (closureBlocked) {
            const notice = document.createElement('span');
            notice.textContent = 'Account ' + item.closureState + ' — username reserved';
            actions.appendChild(notice);
        }

        if (!closureBlocked && item.status === 'pending') {
            actions.appendChild(actionButton('Approve', 'primary', async function () {
                const warning = item.hasRejectedMatches
                    ? 'This request matches an archived rejection. Have you reviewed the matching history and chosen to approve ' + item.username + '?'
                    : 'Approve ' + item.username + ' and queue account creation?';
                if (!window.confirm(warning)) return;
                await request(endpoint + '/' + item.id + '/approve', {
                    method: 'POST', body: JSON.stringify({reviewedRejections: !!item.hasRejectedMatches})
                });
                message.textContent = item.username + ' was queued for approval.';
            }));

            actions.appendChild(actionButton('Reject', '', async function () {
                const reason = window.prompt('Optional rejection note:', '');
                if (reason === null) return;
                await request(endpoint + '/' + item.id + '/reject', {
                    method: 'POST',
                    body: JSON.stringify({reason: reason})
                });
                message.textContent = item.username + ' was rejected and moved to Archived rejections.';
            }));
        }

        if (!closureBlocked && item.status === 'failed') {
            actions.appendChild(actionButton('Retry', 'primary', async function () {
                if (!window.confirm('Queue ' + item.username + ' for another attempt?')) return;
                await request(endpoint + '/' + item.id + '/retry', {method: 'POST', body: '{}'});
                message.textContent = item.username + ' was queued again.';
            }));
        }

        if (!closureBlocked && item.status === 'completed') {
            const resendControls = document.createElement('span');
            resendControls.className = 'covin-resend-controls';

            const resendDays = durationSelect(item.invitationDays);
            resendControls.appendChild(resendDays);
            resendControls.appendChild(actionButton('Resend link', '', async function () {
                const days = Number(resendDays.value);
                const warning = 'Create a replacement ' + days + '-day enrollment link for ' +
                    item.username + '? The old link will stop working. Opening the new single-use ' +
                    'link begins enrollment, and it cannot then be moved to another browser or device.';

                if (!window.confirm(warning)) return;

                await request(endpoint + '/' + item.id + '/resend', {
                    method: 'POST',
                    body: JSON.stringify({invitationDays: days})
                });
                message.textContent = 'A replacement enrollment link for ' + item.username +
                    ' was queued.';
            }));
            actions.appendChild(resendControls);
        }

        const historyRow = tbody.insertRow();
        historyRow.className = 'covin-history-row';

        const historyCell = historyRow.insertCell();
        historyCell.colSpan = 8;
        if (item.hasRejectedMatches) historyCell.appendChild(rejectionMatches(item));
        historyCell.appendChild(historyDetails(item));
    }

    function rejectionMatches(item) {
        const details = document.createElement('details');
        details.className = 'covin-match-warning';
        const summary = document.createElement('summary');
        summary.textContent = 'Matching archived rejection — review before approving';
        details.appendChild(summary);
        const content = document.createElement('div');
        details.appendChild(content);
        let loaded = false;
        let matchPage = 0;
        let busy = false;
        const more = actionButton('Load more matches', '', async function () {
            await loadMatches();
        }, false);
        more.hidden = true;
        details.appendChild(more);

        async function loadMatches() {
            if (busy) return;
            busy = true;
            try {
                const result = await request(endpoint + '/' + item.id + '/matches?page=' + matchPage);
                if (matchPage === 0) content.replaceChildren();
                result.items.forEach(function (match) {
                    const entry = document.createElement('div');
                    entry.className = 'covin-match-entry';
                    const label = document.createElement('p');
                    const fields = [];
                    if (match.username.trim().toLowerCase() === item.username.trim().toLowerCase()) fields.push('username');
                    if (match.contactEmail.trim().toLowerCase() === item.contactEmail.trim().toLowerCase()) fields.push('contact email');
                    label.textContent = 'Request #' + match.id + ': ' + match.displayName + ' (' + match.username +
                        ', ' + match.contactEmail + ') — rejected ' + formatDate(match.reviewedAt) +
                        ' by ' + match.reviewedBy + '. Matching: ' + (fields.join(' and ') || 'database-equivalent identifier') +
                        '. Reason: ' + (match.errorMessage || 'No reason recorded.');
                    entry.appendChild(label);
                    entry.appendChild(historyDetails(match));
                    content.appendChild(entry);
                });
                if (matchPage === 0 && !result.items.length) content.textContent = 'No matching rejections remain.';
                more.hidden = !result.hasMore;
                matchPage++;
                loaded = true;
            } catch (error) {
                message.textContent = error.message;
                if (!loaded) content.textContent = 'Unable to load matches. Close and reopen to retry.';
            } finally {
                busy = false;
            }
        }
        details.addEventListener('toggle', function () {
            if (details.open && !loaded) loadMatches();
        });
        return details;
    }

    async function loadRequests(automatic = false) {
        const sequence = ++loadSequence;
        if (!automatic) {
            previous.disabled = true;
            next.disabled = true;
        }
        try {
            const params = new URLSearchParams({view: view.value, search: searchTerm, page: String(page)});
            const result = await request(browserEndpoint + '?' + params.toString());
            if (sequence !== loadSequence) return;
            if (automatic && (root.querySelector('details[open]') || actionsInFlight || filter.contains(document.activeElement))) return;
            if (!result.items.length && page > 0) {
                page--;
                return loadRequests();
            }
            const requests = result.items;
            tbody.replaceChildren();
            previous.disabled = page === 0;
            next.disabled = !result.hasMore;
            pageLabel.textContent = 'Page ' + (page + 1);

            if (!requests.length) {
                const row = tbody.insertRow();
                const cell = row.insertCell();
                cell.colSpan = 8;
                cell.textContent = view.value === 'rejected' ? 'No archived rejections match this search.' : 'No active requests match this search.';
                return;
            }

            requests.forEach(renderRequest);
        } catch (error) {
            if (sequence === loadSequence) message.textContent = error.message;
        }
    }

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        message.textContent = 'Saving request…';

        try {
            await request(endpoint, {
                method: 'POST',
                body: JSON.stringify({
                    displayName: displayName.value,
                    username: username.value.toLowerCase(),
                    contactEmail: contactEmail.value,
                    invitationDays: Number(invitationDays.value)
                })
            });

            form.reset();
            view.value = 'active';
            search.value = '';
            searchTerm = '';
            page = 0;
            message.textContent = 'Pending request added.';
            await loadRequests();
        } catch (error) {
            message.textContent = error.message;
        }
    });

    refresh.addEventListener('click', function () { loadRequests(); });
    filter.addEventListener('submit', function (event) {
        event.preventDefault();
        searchTerm = search.value.trim();
        page = 0;
        loadRequests();
    });
    view.addEventListener('change', function () {
        page = 0;
        searchTerm = search.value.trim();
        loadRequests();
    });
    previous.addEventListener('click', function () {
        if (page > 0) { page--; loadRequests(); }
    });
    next.addEventListener('click', function () { page++; loadRequests(); });
    loadRequests();
    window.setInterval(function () {
        if (!root.querySelector('details[open]') && !actionsInFlight && !filter.contains(document.activeElement)) {
            loadRequests(true);
        }
    }, 10000);
}());
