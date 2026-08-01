<script>
  import { Input, Label, Alert, Modal, Button, Hr } from '$lib/components/ui';
  import { MapPin, Search } from '@lucide/svelte';
  import * as m from '$lib/paraglide/messages.js';
  import { languageTag } from '$lib/paraglide/runtime.js';

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

  let searchInput = $state('');
  let results = $state([]);
  let searching = $state(false);
  let searchMessage = $state('');
  let modal_open = $state(false);

  // Temp values for modal editing
  let tempVenueName = $state('');
  let tempVenueNameKo = $state('');
  let tempVenueAddress = $state('');
  let tempVenueAddressKo = $state('');
  let tempLatitude = $state(null);
  let tempLongitude = $state(null);
  let formError = $state('');

  const NOMINATIM = 'https://nominatim.openstreetmap.org';

  // Geocoding runs against OpenStreetMap's Nominatim rather than Google Places:
  // it needs no API key and no billing account. Its usage policy caps automated
  // use at roughly one request a second, so this searches on an explicit action
  // rather than on every keystroke the way the old autocomplete did.
  async function searchAddress() {
    const q = searchInput.trim();
    if (!q || searching) return;

    searching = true;
    searchMessage = '';
    results = [];
    try {
      const url = `${NOMINATIM}/search?format=jsonv2&addressdetails=1&limit=5` +
                  `&accept-language=en&q=${encodeURIComponent(q)}`;
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`status ${res.status}`);
      const data = await res.json();
      results = Array.isArray(data) ? data : [];
      if (results.length === 0) searchMessage = m.form_venueSearchNoResults();
    } catch (e) {
      console.error('Nominatim search failed:', e);
      searchMessage = m.form_venueSearchFailed();
    } finally {
      searching = false;
    }
  }

  // Look the chosen object up again by its OSM id in Korean, so both language
  // fields describe the same place. A second search by text could rank a
  // different result first.
  async function fetchKorean(result) {
    const prefix = String(result.osm_type ?? '').charAt(0).toUpperCase();
    if (!prefix || !result.osm_id) return null;
    try {
      const url = `${NOMINATIM}/lookup?format=jsonv2&osm_ids=${prefix}${result.osm_id}` +
                  `&accept-language=ko`;
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) return null;
      const data = await res.json();
      return Array.isArray(data) && data[0] ? data[0] : null;
    } catch (e) {
      console.warn('Korean lookup failed, keeping the English text:', e);
      return null;
    }
  }

  const shortName = (r) =>
    r?.name || String(r?.display_name ?? '').split(',')[0].trim();

  async function selectResult(result) {
    tempLatitude = Number(result.lat);
    tempLongitude = Number(result.lon);
    tempVenueName = shortName(result);
    tempVenueAddress = result.display_name || '';

    // Nominatim falls back to the local name when there is no Korean one, so
    // these can legitimately end up identical to the English fields.
    const ko = await fetchKorean(result);
    tempVenueNameKo = ko ? shortName(ko) : tempVenueName;
    tempVenueAddressKo = ko?.display_name || tempVenueAddress;

    results = [];
    searchInput = '';
    searchMessage = '';
  }

  const hasTempCoords = $derived(
    tempLatitude !== null && tempLatitude !== '' && !Number.isNaN(Number(tempLatitude)) &&
    tempLongitude !== null && tempLongitude !== '' && !Number.isNaN(Number(tempLongitude))
  );

  // Display-only embed: no API key, so no "development purposes only" watermark.
  const previewUrl = $derived(
    hasTempCoords
      ? `https://maps.google.com/maps?q=${Number(tempLatitude)},${Number(tempLongitude)}` +
        `&z=15&hl=${languageTag()}&output=embed`
      : ''
  );

  function openModal() {
    modal_open = true;
    tempVenueName = venueName;
    tempVenueNameKo = venueNameKo;
    tempVenueAddress = venueAddress;
    tempVenueAddressKo = venueAddressKo;
    tempLatitude = venueLatitude;
    tempLongitude = venueLongitude;
    formError = '';
    searchInput = '';
    results = [];
    searchMessage = '';
  }

  function closeModal() {
    modal_open = false;
    formError = '';
  }

  function confirmVenue() {
    if (!tempVenueName.trim() || !tempVenueNameKo.trim() ||
        !tempVenueAddress.trim() || !tempVenueAddressKo.trim()) {
      formError = m.form_venueNameAddressRequired();
      return;
    }
    // Coordinates stay optional, but a half-entered or out-of-range pair would
    // put the map somewhere wrong rather than simply omitting it.
    const lat = Number(tempLatitude);
    const lng = Number(tempLongitude);
    const latGiven = tempLatitude !== null && tempLatitude !== '';
    const lngGiven = tempLongitude !== null && tempLongitude !== '';
    if (latGiven !== lngGiven ||
        (latGiven && (Number.isNaN(lat) || lat < -90 || lat > 90)) ||
        (lngGiven && (Number.isNaN(lng) || lng < -180 || lng > 180))) {
      formError = m.form_venueCoordsInvalid();
      return;
    }

    formError = '';
    venueName = tempVenueName;
    venueNameKo = tempVenueNameKo;
    venueAddress = tempVenueAddress;
    venueAddressKo = tempVenueAddressKo;
    venueLatitude = latGiven ? lat : null;
    venueLongitude = lngGiven ? lng : null;
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
    {#if formError}
      <Alert color="red">{formError}</Alert>
    {/if}

    <!-- Address lookup -->
    <div>
      <Label for="search_address" class="block mb-2">{m.form_searchAddress()}</Label>
      <div class="flex gap-2">
        <div class="relative flex-1">
          <div class="absolute inset-y-0 start-0 flex items-center ps-3.5 pointer-events-none">
            <MapPin class="h-5 w-5 text-gray-500" />
          </div>
          <Input
            id="search_address"
            type="text"
            bind:value={searchInput}
            onkeydown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                searchAddress();
              }
            }}
            placeholder={m.form_searchAddressPlaceholder()}
            class="ps-10"
            size="md"
          />
        </div>
        <Button color="primary" onclick={searchAddress} disabled={searching || !searchInput.trim()}>
          <Search class="w-4 h-4 me-1.5" />
          {searching ? m.common_loading() : m.form_venueSearchButton()}
        </Button>
      </div>

      {#if results.length > 0}
        <div class="mt-2 bg-white border border-gray-300 rounded-lg shadow-sm max-h-60 overflow-y-auto">
          {#each results as result}
            <button
              type="button"
              class="w-full text-left px-4 py-2 hover:bg-gray-100 border-b border-gray-200 last:border-b-0"
              onclick={() => selectResult(result)}
            >
              <div class="font-medium text-sm">{shortName(result)}</div>
              <div class="text-xs text-gray-600">{result.display_name}</div>
            </button>
          {/each}
        </div>
      {/if}

      {#if searchMessage}
        <p class="text-sm text-red-600 mt-2">{searchMessage}</p>
      {/if}

      <p class="text-sm text-gray-500 mt-2">{m.form_searchAddressHint()}</p>
      <p class="text-xs text-gray-400 mt-1">{m.form_venueSearchAttribution()}</p>
    </div>

    {#if previewUrl}
      <iframe
        src={previewUrl}
        title={tempVenueName || m.form_selectVenueLocation()}
        class="w-full h-72 rounded-lg border border-gray-300"
        loading="lazy"
        referrerpolicy="no-referrer-when-downgrade"
      ></iframe>
    {:else}
      <div class="w-full h-72 rounded-lg border border-dashed border-gray-300 flex items-center justify-center text-sm text-gray-500">
        {m.form_venueCoordsHint()}
      </div>
    {/if}

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

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label for="edit_venue_latitude" class="block mb-2">{m.form_venueLatitude()}</Label>
          <Input
            id="edit_venue_latitude"
            type="number"
            step="any"
            bind:value={tempLatitude}
            placeholder="37.5665"
          />
        </div>

        <div>
          <Label for="edit_venue_longitude" class="block mb-2">{m.form_venueLongitude()}</Label>
          <Input
            id="edit_venue_longitude"
            type="number"
            step="any"
            bind:value={tempLongitude}
            placeholder="126.9780"
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
