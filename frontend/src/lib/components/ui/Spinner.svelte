<script>
    let { size = '8', color = 'primary', class: className = '', ...rest } = $props();
    const COLORS = { primary: 'fill-primary-600', gray: 'fill-gray-600', white: 'fill-white' };
</script>

<svg
    class="inline h-{size} w-{size} animate-spin text-gray-200 {COLORS[color] ?? COLORS.primary} {className}"
    viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" {...rest}
>
    <path d="M100 50.59c0 27.61-22.39 50-50 50s-50-22.39-50-50 22.39-50 50-50 50 22.39 50 50Zm-90.92 0c0 22.6 18.32 40.92 40.92 40.92s40.92-18.32 40.92-40.92S72.6 9.67 50 9.67 9.08 27.99 9.08 50.59Z" fill="currentColor"/>
    <path d="M93.97 39.04c2.43-.64 3.89-3.13 3.08-5.51a50 50 0 0 0-10.79-17.94A50 50 0 0 0 38.16 1.16c-2.44.6-3.77 3.1-3.03 5.5.74 2.4 3.26 3.71 5.71 3.16a40.92 40.92 0 0 1 38.68 12.1 40.92 40.92 0 0 1 8.53 14.15c.85 2.37 3.5 3.62 5.92 2.97Z"/>
</svg>
