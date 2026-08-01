<script>
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import * as m from '$lib/paraglide/messages.js';
  import { ExternalLink } from '@lucide/svelte';

  let {
    venueName = '',
    venueAddress = '',
    venueLatitude = null,
    venueLongitude = null
  } = $props();

  let mapContainer;
  let map;
  let marker;
  let loadError = $state('');

  // Google Maps URL for opening in new tab
  let mapsUrl = $derived.by(() => {
    if (!venueLatitude || !venueLongitude) return '';
    return `https://www.google.com/maps/search/?api=1&query=${venueLatitude},${venueLongitude}`;
  });

  // Load Google Maps API
  onMount(() => {
    if (!browser) return;
    if (!venueLatitude || !venueLongitude) return;

    // Check if Google Maps is already loaded or loading
    if (window.__GOOGLE_MAPS_LOADED__ || window.__GOOGLE_MAPS_LOADING__) {
      if (window.google && window.google.maps) {
        initializeMap();
      } else {
        // Wait for it to load
        const checkInterval = setInterval(() => {
          if (window.google && window.google.maps) {
            clearInterval(checkInterval);
            initializeMap();
          }
        }, 100);
      }
      return;
    }

    // Check if Google Maps is already available
    if (window.google && window.google.maps) {
      window.__GOOGLE_MAPS_LOADED__ = true;
      initializeMap();
      return;
    }

    // Mark as loading to prevent duplicate script injection
    window.__GOOGLE_MAPS_LOADING__ = true;

    // Load Google Maps API with Places and Marker libraries
    const script = document.createElement('script');
    const apiKey = import.meta.env.GOOGLE_MAPS_API_KEY || 'YOUR_GOOGLE_MAPS_API_KEY';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places,marker&loading=async`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      window.__GOOGLE_MAPS_LOADED__ = true;
      window.__GOOGLE_MAPS_LOADING__ = false;
      initializeMap();
    };

    script.onerror = () => {
      loadError = 'Failed to load Google Maps API.';
      window.__GOOGLE_MAPS_LOADING__ = false;
    };

    document.head.appendChild(script);
  });

  function initializeMap() {
    if (!mapContainer) return;
    if (!venueLatitude || !venueLongitude) return;

    // Wait for Google Maps API to be fully loaded
    if (!window.google || !window.google.maps || !window.google.maps.Map || !window.google.maps.marker?.AdvancedMarkerElement) {
      setTimeout(() => {
        initializeMap();
      }, 100);
      return;
    }

    try {
      const center = { lat: venueLatitude, lng: venueLongitude };

      map = new google.maps.Map(mapContainer, {
        center: center,
        zoom: 15,
        mapId: 'VENUE_DISPLAY_MAP',
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
      });

      marker = new google.maps.marker.AdvancedMarkerElement({
        position: center,
        map: map,
        title: venueName,
      });
    } catch (error) {
      console.error('Error initializing map:', error);
      loadError = 'Error loading map.';
    }
  }
</script>

{#if venueLatitude && venueLongitude}
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
    {#if loadError}
      <div class="p-4 bg-red-50 text-red-600 text-sm">
        {loadError}
      </div>
    {:else}
      <div class="relative">
        <div bind:this={mapContainer} class="w-full h-64"></div>
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
    {/if}
  </div>
{/if}
