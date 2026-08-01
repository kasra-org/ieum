<script>
    let { color = 'primary', class: className = '', dismissable = false, onclose = undefined, children, ...rest } = $props();

    let open = $state(true);
    const COLORS = {
        primary: 'bg-primary-50 text-primary-800 border-primary-300',
        info:    'bg-blue-50 text-blue-800 border-blue-300',
        gray:    'bg-gray-50 text-gray-800 border-gray-300',
        red:     'bg-red-50 text-red-800 border-red-300',
        green:   'bg-green-50 text-green-800 border-green-300',
        yellow:  'bg-yellow-50 text-yellow-800 border-yellow-300',
        orange:  'bg-orange-50 text-orange-800 border-orange-300',
        blue:    'bg-blue-50 text-blue-800 border-blue-300',
        dark:    'bg-gray-800 text-gray-100 border-gray-700'
    };
</script>

{#if open}
    <div role="alert" class="flex items-start gap-3 rounded-lg border p-4 text-sm {COLORS[color] ?? COLORS.primary} {className}" {...rest}>
        <div class="flex-1">{@render children?.()}</div>
        {#if dismissable}
            <button type="button" aria-label="Close"
                    class="ms-auto -mt-1 rounded p-1 hover:bg-black/5"
                    onclick={() => { open = false; onclose?.(); }}>&times;</button>
        {/if}
    </div>
{/if}
