<script>
  import * as m from '$lib/paraglide/messages.js';
  import { languageTag } from '$lib/paraglide/runtime.js';
  import { ExternalLink } from '@lucide/svelte';

  let {
    venueName = '',
    venueAddress = '',
    venueLatitude = null,
    venueLongitude = null
  } = $props();

  const hasCoords = $derived(venueLatitude != null && venueLongitude != null);

  // Google Maps URL for opening in new tab
  const mapsUrl = $derived(
    hasCoords
      ? `https://www.google.com/maps/search/?api=1&query=${venueLatitude},${venueLongitude}`
      : ''
  );

  // A plain iframe embed rather than the Maps JavaScript API: this needs no API
  // key and no billing account, so it cannot render the "for development
  // purposes only" watermark that an unkeyed/unbilled JS API load produces.
  //
  // This is Google's long-standing `output=embed` URL, not a documented API, so
  // treat it as best-effort. The supported alternative is the Maps Embed API
  // (google.com/maps/embed/v1/place), which is also free of usage charges but
  // does still require a key.
  //
  // Display-only, which is all this widget ever did — centre, one pin, fixed
  // zoom. VenueSelector still uses the JS API because Autocomplete, Place and
  // Geocoder have no keyless equivalent.
  const embedUrl = $derived(
    hasCoords
      ? `https://maps.google.com/maps?q=${venueLatitude},${venueLongitude}` +
        `&z=15&hl=${languageTag()}&output=embed`
      : ''
  );
</script>

{#if hasCoords}
  <div class="bg-gray-50 border border-gray-200 rounded-lg shadow-sm overflow-hidden">
    <div class="p-4 bg-white border-b border-gray-200">
      <h3 class="text-sm font-semibold text-gray-900">{m.eventDetail_location()}</h3>
      {#if venueName}
        <p class="text-sm text-gray-700 mt-1">{venueName}</p>
      {/if}
      {#if venueAddress}
        <p class="text-xs text-gray-600 mt-1">{venueAddress}</p>
      {/if}
    </div>
    <div class="relative">
      <iframe
        src={embedUrl}
        title={venueName || m.eventDetail_location()}
        class="w-full h-64 border-0"
        loading="lazy"
        allowfullscreen
        referrerpolicy="no-referrer-when-downgrade"
      ></iframe>
      <a
        href={mapsUrl}
        target="_blank"
        rel="noopener noreferrer"
        class="absolute top-2 right-2 bg-white hover:bg-gray-50 shadow-md rounded-lg px-3 py-2 text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1.5 transition-colors"
      >
        {m.venue_viewOnMaps()}
        <ExternalLink class="w-3.5 h-3.5" />
      </a>
    </div>
  </div>
{/if}
