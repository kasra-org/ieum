<script>
  import { Heading, Input, ButtonGroup, InputAddon, Button, Textarea, Select, Label, Alert } from '$lib/components/ui';
  import * as m from '$lib/paraglide/messages.js';
  import InstitutionLookup from '$lib/components/InstitutionLookup.svelte';
  import EmailManagement from '$lib/components/EmailManagement.svelte';

  // Props to accept form data and errors from parent
  export let data = {
    first_name: '',
    middle_initial: '',
    korean_name: '',
    last_name: '',
    nationality: undefined,
    institute: '',
    department: '',
    job_title: '',
    disability: '',
    dietary: '',
    email: '',
    password: '',
    confirm_password: '',
    orcid: '',
    google: '',
  };
  export let errors = {};
  export let config = {};
  export let institution_resolved = null;
  export let instituteDisplayName = '';
  export let emails = [];
  export let onPrimaryChanged = () => {};

  function linkProvider(provider) {
    let formData = {
      provider: provider,
      process: 'connect',
      callback_url: config.action?`/${config.action}?next=${config.next}`:config.next,
      csrfmiddlewaretoken: config.csrf_token,
    };
    // create a form element
    let form = document.createElement('form');
    form.setAttribute('method', 'POST');
    form.setAttribute('action', '/_allauth/browser/v1/auth/provider/redirect');
    form.style.display = 'hidden';
    // append the form to the body
    document.body.appendChild(form);
    // add the data to the form
    for (let key in formData) {
      let input = document.createElement('input');
      input.setAttribute('type', 'hidden');
      input.setAttribute('name', key);
      input.setAttribute('value', formData[key]);
      form.appendChild(input);
    }
    // submit the form
    form.submit();
  }

  function unlinkProvider(provider, account) {
    fetch('/_allauth/browser/v1/account/providers', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': config.csrf_token,
      },
      body: JSON.stringify({
        provider: provider,
        account: account,
      }),
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to unlink ${provider}`);
      }
      if (provider === 'orcid') {
        data.orcid = '';
      } else if (provider === 'google') {
        data.google = '';
      }
    })
    .catch(error => {
      console.error(error);
    });
  }
</script>
  
{#if !config.hide_login_info}
<!-- Login Information -->
<Heading tag="h2" class="text-lg font-bold mb-6">{m.form_personalInfo()}</Heading>
{#if config.hide_password && emails.length > 0}
<div class="mb-6">
  <EmailManagement
    {emails}
    csrf_token={config.csrf_token}
    {onPrimaryChanged}
  />
</div>
{:else}
<div class="mb-6">
  <Label for="email" class="block mb-2 text-dark">{m.form_email()} <span class="text-red-500">*</span></Label>
  <Input type="email" id="email" name="email" bind:value={data.email} disabled={config.hide_password} />
  {#if errors.email}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.email}</p>
    </Alert>
  {/if}
</div>
{/if}
{#if config.hide_password}
<div class="mb-6">
  <Label for="orcid" class="block mb-2 text-dark">{m.form_orcid()}</Label>
  <ButtonGroup class="w-full">
    <Input id="orcid" name="orcid" bind:value={data.orcid} disabled />
      {#if data.orcid}
      <Button onclick={() => unlinkProvider('orcid', data.orcid)} class="w-40" style="background-color: #A6CE39; color: white;">
        {m.form_unlinkOrcid()}
      </Button>
      {:else}
      <Button onclick={() => linkProvider('orcid')} class="w-40" style="background-color: #A6CE39; color: white;">
        {m.form_linkOrcid()}
      </Button>
      {/if}
  </ButtonGroup>
  {#if errors.orcid}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.orcid}</p>
    </Alert>
  {/if}
</div>
<div class="mb-6">
  <Label for="google" class="block mb-2 text-dark">{m.form_google()}</Label>
  <ButtonGroup class="w-full">
    <Input id="google" name="google" bind:value={data.google} disabled />
      {#if data.google}
      <Button onclick={() => unlinkProvider('google', data.google)} color="light" class="w-40">
        {m.form_unlinkGoogle()}
      </Button>
      {:else}
      <Button onclick={() => linkProvider('google')} color="light" class="w-40">
        {m.form_linkGoogle()}
      </Button>
      {/if}
  </ButtonGroup>
  {#if errors.google}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.google}</p>
    </Alert>
  {/if}
</div>
{/if}
{#if !config.hide_password}
<div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
  <div class="mb-6">
    <Label for="password" class="block mb-2">{m.form_password()} <span class="text-red-500">*</span></Label>
    <Input id="password" name="password" type="password" bind:value={data.password} />
    {#if errors.password}
      <Alert type="error" color="red" class="mb-6 mt-3">
        <p class="text-sm">{errors.password}</p>
      </Alert>
    {/if}
  </div>
  <div class="mb-6">
    <Label for="confirm_password" class="block mb-2">{m.form_confirmPassword()} <span class="text-red-500">*</span></Label>
    <Input id="confirm_password" name="confirm_password" type="password" bind:value={data.confirm_password} />
    {#if errors.confirm_password}
      <Alert type="error" color="red" class="mb-6 mt-3">
        <p class="text-sm">{errors.confirm_password}</p>
      </Alert>
    {/if}
  </div>
</div>
{/if}
{/if}

<div class="mb-6">
  <Label for="nationality" class="block mb-2">{m.form_nationality()} <span class="text-red-500">*</span></Label>
  <Select id="nationality" name="nationality" bind:value={data.nationality} items={
    [
      { value: "1", name: m.form_nationalityKorean() },
      { value: "2", name: m.form_nationalityNonKorean() },
      { value: "3", name: m.form_nationalityPreferNot() },
    ]
  } />
  {#if errors.nationality}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.nationality}</p>
    </Alert>
  {/if}
</div>

{#if config.show_english_name || data.nationality === '2' || data.nationality === '3'}
<div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
  <div class="mb-6">
    <Label for="first_name" class="block mb-2">{m.form_firstName()} <span class="text-red-500">*</span></Label>
    <Input id="first_name" name="first_name" bind:value={data.first_name} placeholder="John" />
    {#if errors.first_name}
      <Alert type="error" color="red" class="mb-6 mt-3">
        <p class="text-sm">{errors.first_name}</p>
      </Alert>
    {/if}
  </div>
  <div class="mb-6">
    <Label for="middle_initial" class="block mb-2">{m.form_middleInitial()}</Label>
    <Input id="middle_initial" name="middle_initial" maxlength="1" bind:value={data.middle_initial} />
  </div>
  <div class="mb-6">
    <Label for="last_name" class="block mb-2">{m.form_lastName()} <span class="text-red-500">*</span></Label>
    <Input id="last_name" name="last_name" bind:value={data.last_name} placeholder="Doe" />
    {#if errors.last_name}
      <Alert type="error" color="red" class="mb-6 mt-3">
        <p class="text-sm">{errors.last_name}</p>
      </Alert>
    {/if}
  </div>
</div>
{/if}

{#if config.show_korean_name || data.nationality === '1' || data.nationality === '2' || data.nationality === '3'}
<div class="mb-6">
  <Label for="korean_name" class="block mb-2">{m.form_koreanName()} {#if data.nationality === '1'}<span class="text-red-500">*</span>{/if}</Label>
  <Input id="korean_name" name="korean_name" bind:value={data.korean_name} placeholder="홍길동" />
  {#if errors.korean_name}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.korean_name}</p>
    </Alert>
  {/if}
</div>
{/if}

<!-- Additional Information -->
<hr class="my-8 border-gray-200" />
<Heading tag="h2" class="text-lg font-bold mb-6">{m.form_additionalInfo()}</Heading>
<div class="mb-6">
  <InstitutionLookup bind:value={data.institute} bind:displayName={instituteDisplayName} error={errors.institute} required={true} institution_resolved={institution_resolved} />
</div>

<div class="mb-6">
  <Label for="department" class="block mb-2">{m.form_department()}</Label>
  <Input id="department" name="department" bind:value={data.department} />
</div>

<div class="mb-6">
  <Label for="job_title" class="block mb-2">{m.form_jobTitle()} <span class="text-red-500">*</span></Label>
  <Input id="job_title" name="job_title" bind:value={data.job_title} />
  {#if errors.job_title}
    <Alert type="error" color="red" class="mb-6 mt-3">
      <p class="text-sm">{errors.job_title}</p>
    </Alert>
  {/if}
</div>

<div class="mb-6">
  <Label for="disability" class="block mb-2">{m.form_disability()}</Label>
  <Textarea id="disability" name="disability" value={data.disability} class="w-full" />
</div>

<div class="mb-6">
  <Label for="dietary" class="block mb-2">{m.form_dietary()}</Label>
  <Textarea id="dietary" name="dietary" value={data.dietary} class="w-full" />
</div>