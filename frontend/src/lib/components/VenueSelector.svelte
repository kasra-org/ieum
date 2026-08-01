<script>
  import { Input, Label, Alert, Modal, Button, Hr } from '$lib/components/ui';
  import { MapPin } from '@lucide/svelte';
  import * as m from '$lib/paraglide/messages.js';
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';

  let {
    venueName = $bindable(''),
    venueNameKo = $bindable(''),
    venueAddress = $bindable(''),
    venueAddressKo = $bindable(''),
    venueLatitude = $bindable(null),
    venueLongitude = $bindable(null),
    error = null,
    required = false
  } = $props();

  let mapContainer;
  let map;
  let marker;
  let searchInput = $state('');
  let predictions = $state([]);
  let showPredictions = $state(false);
  let modal_open = $state(false);
  let loadError = $state('');

  // Temp values for modal editing
  let tempVenueName = $state('');
  let tempVenueNameKo = $state('');
  let tempVenueAddress = $state('');
  let tempVenueAddressKo = $state('');
  let tempLatitude = $state(null);
  let tempLongitude = $state(null);
  let formError = $state('');

  // Load Google Maps API
  onMount(() => {
    if (!browser) return;

    // Check if Google Maps is already loaded or loading
    if (window.__GOOGLE_MAPS_LOADED__ || window.__GOOGLE_MAPS_LOADING__) {
      return;
    }

    // Check if Google Maps is already available
    if (window.google && window.google.maps) {
      window.__GOOGLE_MAPS_LOADED__ = true;
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
    };

    script.onerror = () => {
      loadError = 'Failed to load Google Maps API. Please check your API key.';
      window.__GOOGLE_MAPS_LOADING__ = false;
    };

    document.head.appendChild(script);
  });

  function initializeMap() {
    if (!mapContainer) return;

    // Wait for Google Maps API to be fully loaded
    if (!window.google || !window.google.maps || !window.google.maps.Map || !window.google.maps.marker?.AdvancedMarkerElement) {
      loadError = 'Google Maps API is still loading. Please wait...';
      // Retry after a short delay
      setTimeout(() => {
        loadError = '';
        initializeMap();
      }, 500);
      return;
    }

    try {
      // Initialize map
      const center = tempLatitude && tempLongitude
        ? { lat: tempLatitude, lng: tempLongitude }
        : { lat: 37.5665, lng: 126.9780 }; // Default to Seoul

      map = new google.maps.Map(mapContainer, {
        center: center,
        zoom: 15,
        mapId: 'VENUE_SELECTOR_MAP',
      });

      // Add marker if coordinates exist
      if (tempLatitude && tempLongitude) {
        marker = new google.maps.marker.AdvancedMarkerElement({
          position: { lat: tempLatitude, lng: tempLongitude },
          map: map,
          gmpDraggable: true,
        });

        marker.addListener('dragend', (event) => {
          tempLatitude = event.latLng.lat();
          tempLongitude = event.latLng.lng();
          reverseGeocode(tempLatitude, tempLongitude);
        });
      }
    } catch (error) {
      console.error('Error initializing map:', error);
      loadError = 'Error initializing map. Please try again.';
    }
  }

  async function handleSearchInput() {
    if (!searchInput || searchInput.length < 3) {
      predictions = [];
      showPredictions = false;
      return;
    }

    try {
      const request = {
        input: searchInput,
        includedPrimaryTypes: ['establishment'],
      };

      const { suggestions } = await google.maps.places.AutocompleteSuggestion.fetchAutocompleteSuggestions(request);

      if (suggestions && suggestions.length > 0) {
        predictions = suggestions;
        showPredictions = true;
      } else {
        predictions = [];
        showPredictions = false;
      }
    } catch (error) {
      console.error('Error fetching autocomplete suggestions:', error);
      predictions = [];
      showPredictions = false;
    }
  }

  async function selectPlace(suggestion) {
    try {
      // Get placeId for fetching in different languages
      const placeId = suggestion.placePrediction.placeId;

      // Fetch place details to get location first
      const place = suggestion.placePrediction.toPlace();
      await place.fetchFields({
        fields: ['displayName', 'location'],
      });

      const lat = place.location.lat();
      const lng = place.location.lng();

      // Set coordinates immediately
      tempLatitude = lat;
      tempLongitude = lng;

      // Update map
      map.setCenter(place.location);
      map.setZoom(15);

      // Update or create marker
      if (marker) {
        marker.position = place.location;
      } else {
        marker = new google.maps.marker.AdvancedMarkerElement({
          position: place.location,
          map: map,
          gmpDraggable: true,
        });

        marker.addListener('dragend', (event) => {
          tempLatitude = event.latLng.lat();
          tempLongitude = event.latLng.lng();
          reverseGeocode(tempLatitude, tempLongitude);
        });
      }

      // Fetch place name in English using new Places API
      // requestedLanguage is passed when constructing the Place object
      try {
        const placeEn = new google.maps.places.Place({
          id: placeId,
          requestedLanguage: 'en',
        });
        await placeEn.fetchFields({ fields: ['displayName'] });
        tempVenueName = placeEn.displayName || place.displayName || '';
      } catch (e) {
        console.warn('Failed to fetch English name:', e);
        tempVenueName = place.displayName || '';
      }

      // Fetch place name in Korean using new Places API
      try {
        const placeKo = new google.maps.places.Place({
          id: placeId,
          requestedLanguage: 'ko',
        });
        await placeKo.fetchFields({ fields: ['displayName'] });
        tempVenueNameKo = placeKo.displayName || place.displayName || '';
      } catch (e) {
        console.warn('Failed to fetch Korean name:', e);
        tempVenueNameKo = place.displayName || '';
      }

      // Use Geocoder to get bilingual addresses (Geocoder supports language parameter)
      const geocoder = new google.maps.Geocoder();
      const latlng = { lat, lng };

      // Get English address
      geocoder.geocode({ location: latlng, language: 'en' }, (results, status) => {
        if (status === 'OK' && results[0]) {
          tempVenueAddress = results[0].formatted_address;
        }
      });

      // Get Korean address
      geocoder.geocode({ location: latlng, language: 'ko' }, (results, status) => {
        if (status === 'OK' && results[0]) {
          tempVenueAddressKo = results[0].formatted_address;
        }
      });

      // Clear search input and hide predictions
      searchInput = '';
      predictions = [];
      showPredictions = false;
      loadError = '';
    } catch (error) {
      console.error('Error getting place details:', error);
      loadError = 'Failed to get place details. Please try again.';
    }
  }

  function reverseGeocode(lat, lng) {
    const geocoder = new google.maps.Geocoder();
    const latlng = { lat: lat, lng: lng };

    // Get address in English
    geocoder.geocode({ location: latlng, language: 'en' }, (results, status) => {
      if (status === 'OK') {
        if (results[0]) {
          tempVenueAddress = results[0].formatted_address;
        }
      }
    });

    // Get address in Korean
    geocoder.geocode({ location: latlng, language: 'ko' }, (results, status) => {
      if (status === 'OK') {
        if (results[0]) {
          const koreanAddress = results[0].formatted_address;
          tempVenueAddressKo = koreanAddress !== tempVenueAddress ? koreanAddress : '';
        }
      }
    });
  }

  function openModal() {
    modal_open = true;
    // Initialize temp values from current values
    tempVenueName = venueName;
    tempVenueNameKo = venueNameKo;
    tempVenueAddress = venueAddress;
    tempVenueAddressKo = venueAddressKo;
    tempLatitude = venueLatitude;
    tempLongitude = venueLongitude;
    formError = '';
    // Initialize map when modal opens
    setTimeout(() => {
      initializeMap();
    }, 100);
  }

  function closeModal() {
    modal_open = false;
    formError = '';
  }

  function confirmVenue() {
    // Validate required fields
    if (!tempVenueName.trim() || !tempVenueNameKo.trim() || !tempVenueAddress.trim() || !tempVenueAddressKo.trim()) {
      formError = m.form_venueNameAddressRequired();
      return;
    }
    formError = '';
    // Set the actual values from temp values
    venueName = tempVenueName;
    venueNameKo = tempVenueNameKo;
    venueAddress = tempVenueAddress;
    venueAddressKo = tempVenueAddressKo;
    venueLatitude = tempLatitude;
    venueLongitude = tempLongitude;
    closeModal();
  }

</script>

<div class="space-y-4">
  <div>
    <Label for="venue_address" class="block mb-2">
      {m.form_venueAddress()} {#if required}<span class="text-red-500">*</span>{/if}
    </Label>
    <Input
      id="venue_address"
      name="venue_address"
      type="text"
      value={venueAddress}
      placeholder={m.form_venueAddressPlaceholder()}
      class="cursor-pointer"
      readonly
      onclick={openModal}
    />
  </div>

  <div>
    <Label for="venue_address_ko" class="block mb-2">
      {m.form_venueAddressKo()} {#if required}<span class="text-red-500">*</span>{/if}
    </Label>
    <Input
      id="venue_address_ko"
      name="venue_address_ko"
      type="text"
      value={venueAddressKo}
      placeholder={m.form_venueAddressPlaceholder()}
      required={required}
      readonly
      class="cursor-pointer"
      onclick={openModal}
    />
  </div>

  <div>
    <Label for="venue_name" class="block mb-2">
      {m.form_venueName()} {#if required}<span class="text-red-500">*</span>{/if}
    </Label>
    <Input
      id="venue_name"
      name="venue"
      type="text"
      value={venueName}
      placeholder={m.form_venueNamePlaceholder()}
      required={required}
      readonly
      class="cursor-pointer"
      onclick={openModal}
    />
  </div>

  <div>
    <Label for="venue_name_ko" class="block mb-2">
      {m.form_venueNameKo()} {#if required}<span class="text-red-500">*</span>{/if}
    </Label>
    <Input
      id="venue_name_ko"
      name="venue_ko"
      type="text"
      value={venueNameKo}
      placeholder={m.form_venueNameKo()}
      required={required}
      readonly
      class="cursor-pointer"
      onclick={openModal}
    />
  </div>
  {#if venueLatitude && venueLongitude}
    <input type="hidden" name="venue_latitude" value={venueLatitude} />
    <input type="hidden" name="venue_longitude" value={venueLongitude} />
  {/if}

  {#if error}
    <Alert color="red" class="mt-3">
      <p class="text-sm">{error}</p>
    </Alert>
  {/if}
</div>

<Modal title={m.form_selectVenueLocation()} bind:open={modal_open} size="xl" outsideclose={false}>
  <div class="space-y-4">
    {#if loadError || formError}
      <Alert color="red">{loadError || formError}</Alert>
    {/if}

    <!-- Map Selection Section -->
    <div class="relative">
      <Label for="search_address" class="block mb-2">{m.form_searchAddress()}</Label>
      <div class="relative">
        <div class="absolute inset-y-0 start-0 flex items-center ps-3.5 pointer-events-none">
          <MapPin class="h-5 w-5 text-gray-500" />
        </div>
        <Input
          id="search_address"
          type="text"
          bind:value={searchInput}
          oninput={handleSearchInput}
          onfocus={() => { if (predictions.length > 0) showPredictions = true; }}
          onkeydown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              if (predictions.length > 0) {
                selectPlace(predictions[0]);
              }
            }
          }}
          placeholder={m.form_searchAddressPlaceholder()}
          class="ps-10"
          size="md"
        />
      </div>

      {#if showPredictions && predictions.length > 0}
        <div class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {#each predictions as suggestion}
            <button
              type="button"
              class="w-full text-left px-4 py-2 hover:bg-gray-100 border-b border-gray-200 last:border-b-0"
              onclick={() => selectPlace(suggestion)}
            >
              <div class="font-medium text-sm">{suggestion.placePrediction.mainText?.text || suggestion.placePrediction.text?.text || ''}</div>
              <div class="text-xs text-gray-600">{suggestion.placePrediction.secondaryText?.text || ''}</div>
            </button>
          {/each}
        </div>
      {/if}

      <p class="text-sm text-gray-500 mt-2">{m.form_searchAddressHint()}</p>
    </div>

    <div bind:this={mapContainer} class="w-full h-72 rounded-lg border border-gray-300"></div>

    <p class="text-sm text-gray-600">
      {m.form_dragMarkerHint()}
    </p>

    <Hr class="my-4" />

    <!-- Name/Address Editing Section -->
    <div class="space-y-4">
      <div>
        <Label for="edit_venue_address" class="block mb-2">{m.form_venueAddress()} <span class="text-red-500">*</span></Label>
        <Input
          id="edit_venue_address"
          type="text"
          bind:value={tempVenueAddress}
          placeholder={m.form_venueAddressPlaceholder()}
          required
        />
      </div>

      <div>
        <Label for="edit_venue_address_ko" class="block mb-2">{m.form_venueAddressKo()} <span class="text-red-500">*</span></Label>
        <Input
          id="edit_venue_address_ko"
          type="text"
          bind:value={tempVenueAddressKo}
          placeholder={m.form_venueAddressPlaceholder()}
          required
        />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label for="edit_venue_name" class="block mb-2">{m.form_venueName()} <span class="text-red-500">*</span></Label>
          <Input
            id="edit_venue_name"
            type="text"
            bind:value={tempVenueName}
            placeholder={m.form_venueNamePlaceholder()}
            required
          />
        </div>

        <div>
          <Label for="edit_venue_name_ko" class="block mb-2">{m.form_venueNameKo()} <span class="text-red-500">*</span></Label>
          <Input
            id="edit_venue_name_ko"
            type="text"
            bind:value={tempVenueNameKo}
            placeholder={m.form_venueNameKo()}
            required
          />
        </div>
      </div>
    </div>
  </div>

  {#snippet footer()}
    <div class="flex justify-end gap-2 w-full">
      <Button color="alternative" onclick={closeModal}>{m.common_cancel()}</Button>
      <Button color="primary" onclick={confirmVenue}>{m.common_confirm()}</Button>
    </div>
  {/snippet}
</Modal>
