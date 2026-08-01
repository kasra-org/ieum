/**
 * Stand-in for flowbite-svelte's `uiHelpers`, which returns a small open/close
 * controller. Only the open/close/toggle surface was used here.
 */
export function uiHelpers() {
    let open = $state(false);
    return {
        get isOpen() { return open; },
        set isOpen(v) { open = v; },
        toggle: () => (open = !open),
        open: () => (open = true),
        close: () => (open = false)
    };
}
