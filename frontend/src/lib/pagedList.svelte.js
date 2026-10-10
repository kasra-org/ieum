import { untrack } from 'svelte';

// Ids per request when fetching a selection: well inside URL length limits.
const ID_BATCH = 200;

/**
 * One server-paginated admin list.
 *
 * The admin tables used to receive every row from the page load and page,
 * search and count in the browser; with thousands of registrations that was
 * the slowest part of the page. Each table now holds one of these instead: it
 * asks a relay route (src/routes/api/...) for the page on screen, sends the
 * search and filters along, and keeps the figures the server returns beside
 * the rows - `counts` for filter chips, `summary` for totals.
 *
 * The relay answers {items, total, offset, limit, counts?, summary?}; the same
 * URL with /export appended answers every matching row unpaged, for the
 * actions that work on the whole list (CSV, email to all, certificates).
 *
 * Usage, in a component's <script>:
 *
 *     const list = new PagedList(() => `/api/event/${data.event.id}/attendees`,
 *                                { filters: { status: 'registered' } });
 *     list.track(() => data);   // load now, and again whenever the page data reloads
 *
 * then bind the search box to `list.search` / `list.field`, render
 * `list.items`, and hand TablePagination `list.page`, `list.totalPages` and
 * `p => list.goto(p)`.
 */
export class PagedList {
    items = $state([]);
    total = $state(0);
    counts = $state({});
    summary = $state({});
    page = $state(1);
    search = $state('');
    field = $state('all');
    filters = $state({});
    // True from the start: the first page is always on its way, and a page
    // rendered on the server must show that rather than "no records".
    loading = $state(true);
    error = $state('');
    // False until the first page arrives: counts read as zero until then,
    // so a table shows a placeholder rather than "0".
    loaded = $state(false);

    #sequence = 0;
    #timer = null;
    #url;
    // What a request asks for, apart from its page: the search and the
    // filters. The field picker alone with nothing typed, or a space added,
    // asks for nothing new.
    //   #shown - the request whose rows are on screen, set only on success,
    //            so a failure can put the pager back where those rows are;
    //   #issued - the latest request sent, so the search box can tell a
    //            change from a return to what is already on its way.
    #shown = { key: null, page: 1 };
    #issued = null;

    // Built from what params() actually sends: an empty filter is no filter,
    // and the order filters were set in does not matter.
    #requestKey() {
        const term = this.search.trim();
        const filters = Object.entries(this.filters)
            .filter(([, value]) => value !== undefined && value !== null && value !== '')
            .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
        return JSON.stringify([term ? this.field || 'all' : '', term, filters]);
    }

    /**
     * `url` is the relay route, or a function returning it - pass
     * `() => \`/api/event/${data.event.id}/...\`` so it follows the page's
     * data instead of keeping the event it was created with.
     */
    constructor(url, { pageSize = 10, filters = {} } = {}) {
        this.#url = url;
        this.pageSize = pageSize;
        this.filters = filters;
    }

    get url() {
        return typeof this.#url === 'function' ? this.#url() : this.#url;
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.total / this.pageSize));
    }

    /** The search and filters as query parameters, plus `extra`. */
    params(extra = {}) {
        const params = new URLSearchParams();
        const term = this.search.trim();
        if (term) {
            params.set('search', term);
            params.set('field', this.field || 'all');
        }
        for (const [key, value] of Object.entries({ ...this.filters, ...extra })) {
            if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
        }
        return params;
    }

    /**
     * Fetch the current page. A slower, older answer never overwrites a newer
     * one. A request for a different search or filter starts at its first
     * page; a failed one leaves the rows on screen and puts the pager back
     * on their page, and the error stays until a load succeeds.
     */
    async load() {
        // Whatever is loading now carries the current search, so a reload
        // still waiting on the typing pause would only repeat it.
        clearTimeout(this.#timer);
        const key = this.#requestKey();
        if (key !== this.#shown.key) this.page = 1;
        this.#issued = key;
        const sequence = ++this.#sequence;
        this.loading = true;
        const fail = (message) => {
            if (sequence !== this.#sequence) return;
            this.error = message;
            this.page = this.#shown.page;
            // So asking for it again - even by retyping it - is a retry.
            this.#issued = this.#shown.key;
        };
        try {
            const params = this.params({ offset: (this.page - 1) * this.pageSize, limit: this.pageSize });
            let response, body;
            try {
                response = await fetch(`${this.url}?${params}`, { headers: { Accept: 'application/json' } });
                body = await response.json().catch(() => ({}));
            } catch (error) {
                // Offline, or the connection dropped.
                fail(error?.message || 'network error');
                return;
            }
            if (sequence !== this.#sequence) return;
            if (!response.ok) {
                fail(body?.message || `${response.status}`);
                return;
            }
            this.error = '';
            this.items = body.items ?? [];
            this.total = body.total ?? 0;
            this.counts = body.counts ?? {};
            this.summary = body.summary ?? {};
            this.loaded = true;
            // The last row of the last page went (deleted, or moved to another
            // tab): show the page that now holds the end of the list. Its
            // page is the one to fall back to should that load fail.
            if (this.items.length === 0 && this.page > 1 && this.total > 0) {
                this.#shown = { key, page: this.totalPages };
                this.page = this.totalPages;
                return this.load();
            }
            this.#shown = { key, page: this.page };
        } finally {
            if (sequence === this.#sequence) this.loading = false;
        }
    }

    goto(page) {
        this.page = Math.min(Math.max(1, page), this.totalPages);
        return this.load();
    }

    /** Change one filter (a tab, a chip); load() starts it at page 1. */
    setFilter(name, value) {
        this.filters = { ...this.filters, [name]: value };
        return this.load();
    }

    /** Every row matching the current search and filters, from /export. */
    async exportAll(extra = {}) {
        const response = await fetch(`${this.url}/export?${this.params(extra)}`, {
            headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error(`${response.status}`);
        return response.json();
    }

    /**
     * The given rows (by id), whichever pages they are on - for a selection.
     * `extra` narrows them further (status: 'registered' keeps only those
     * still on the roster). Asked for in batches: a selection of thousands
     * would not fit in one URL.
     */
    async fetchByIds(ids, extra = {}) {
        const rows = [];
        for (let start = 0; start < ids.length; start += ID_BATCH) {
            const params = new URLSearchParams({ ...extra, ids: ids.slice(start, start + ID_BATCH).join(',') });
            const response = await fetch(`${this.url}/export?${params}`, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error(`${response.status}`);
            rows.push(...await response.json());
        }
        return rows;
    }

    /**
     * Wire the list to the component. Call once during component setup:
     * loads now; reloads when `dependency` changes (pass `() => data`, so
     * the save actions' `update()` refreshes the table as it used to); and
     * reloads from page 1 a moment after the search box stops changing.
     */
    track(dependency) {
        let started = false;
        $effect(() => {
            this.search;
            this.field;
            untrack(() => {
                if (!started) return;
                clearTimeout(this.#timer);
                // Nothing new to ask - unless the last attempt failed, when
                // any change to the box is a retry.
                if (this.#requestKey() === this.#issued && !this.error) return;
                // load() starts a changed search at page 1 itself.
                this.#timer = setTimeout(() => this.load(), 250);
            });
            // A search still waiting when the tab closes is dropped with it.
            return () => clearTimeout(this.#timer);
        });
        $effect(() => {
            dependency?.();
            untrack(() => {
                started = true;
                this.load();
            });
        });
    }
}
