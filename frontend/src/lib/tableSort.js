/**
 * Sorting by column header, shared by every searchable table.
 *
 * A sort is a list of {key, dir} - the first entry decides, the next breaks
 * its ties, and so on. A click on a header cycles that column ascending,
 * descending, then off. Without Shift the column becomes the only sort;
 * with Shift it is added to the ones already set, or changed or removed
 * among them, keeping their order of priority.
 *
 * Server-paginated tables send the sort as `order` (orderParam) and Django
 * orders the whole list before paging it; tables that hold all their rows
 * sort them here with sortRows.
 */

export function nextSort(sort, key, additive) {
    const current = sort.find(s => s.key === key);
    const dir = !current ? 'asc' : current.dir === 'asc' ? 'desc' : null;
    if (!additive) return dir ? [{ key, dir }] : [];
    if (!current) return [...sort, { key, dir }];
    return dir ? sort.map(s => (s.key === key ? { key, dir } : s)) : sort.filter(s => s.key !== key);
}

/** The sort as the API takes it: `name,-email` - a minus for descending. */
export const orderParam = (sort) => sort.map(s => (s.dir === 'desc' ? '-' : '') + s.key).join(',');

const collator = new Intl.Collator(['ko', 'en'], { numeric: true, sensitivity: 'base' });
const isEmpty = (value) => value === null || value === undefined || value === '';

/**
 * `rows` in the order `sort` asks for; `valueOf(row, key)` reads a column.
 * Text compares as people read it (case aside, numbers by value), numbers
 * and booleans by value; blanks go last whichever the direction, as the
 * server sorts them. Rows that tie keep the order they came in.
 */
export function sortRows(rows, sort, valueOf) {
    if (!sort.length) return rows;
    return rows
        .map((row, index) => ({ row, index }))
        .sort((x, y) => {
            for (const { key, dir } of sort) {
                const a = valueOf(x.row, key);
                const b = valueOf(y.row, key);
                if (isEmpty(a) || isEmpty(b)) {
                    if (isEmpty(a) && isEmpty(b)) continue;
                    return isEmpty(a) ? 1 : -1;
                }
                const order = (typeof a === 'number' || typeof a === 'boolean') && typeof a === typeof b
                    ? Number(a) - Number(b)
                    : collator.compare(String(a), String(b));
                if (order) return dir === 'desc' ? -order : order;
            }
            return x.index - y.index;
        })
        .map(({ row }) => row);
}
