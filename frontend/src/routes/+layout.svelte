<script>
	import "../app.css";
	let { children, data } = $props();
	import {
		Navbar,
		NavBrand,
		Avatar,
		Dropdown,
		DropdownHeader,
		DropdownItem,
		DropdownDivider,
		Button,
		Spinner,
	} from '$lib/components/ui';
	import { Globe } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { languageTag, setLanguageTag, onSetLanguageTag } from '$lib/paraglide/runtime.js';
	import * as m from '$lib/paraglide/messages.js';
	import CookieConsent from '$lib/components/CookieConsent.svelte';

	const languages = [
		{ code: 'en', name: 'English' },
		{ code: 'ko', name: '한국어' }
	];

	let currentLanguage = $state(languageTag());
	let profileDropdownOpen = $state(false);
	let languageDropdownOpen = $state(false);
	let isLoading = $state(true);

	onMount(() => {
		// Set up callback to update state when language changes
		onSetLanguageTag((newTag) => {
			currentLanguage = newTag;
		});

		const savedLocale = localStorage.getItem('preferred-locale');

		if (!savedLocale) {
			const browserLanguage = navigator.language.toLowerCase();
			const supportedLanguages = ['en', 'ko'];

			let detectedLanguage = supportedLanguages.find(lang =>
				browserLanguage === lang || browserLanguage.startsWith(lang + '-')
			);

			if (!detectedLanguage) {
				detectedLanguage = 'en';
			}

			setLanguageTag(detectedLanguage);
			localStorage.setItem('preferred-locale', detectedLanguage);
		} else {
			setLanguageTag(savedLocale);
		}

		// Update current language state after setting
		currentLanguage = languageTag();

		// Mark loading as complete
		isLoading = false;
	});

	function switchLanguage(newLocale) {
		setLanguageTag(newLocale);
		localStorage.setItem('preferred-locale', newLocale);
		document.documentElement.lang = newLocale;
	}

	// Compute the next parameter for login/registration
	// If user is on email verification page, redirect to root after login
	let nextPath = $derived(
		$page.url.pathname.includes('/verify-email') ? '/' : $page.url.pathname
	);

	// Check if current page is a receipt page (hide header/footer for printing)
	let isReceiptPage = $derived($page.url.pathname.startsWith('/receipt/'));

	// Business details card issuers require to be published as text in the
	// footer (상호명 / 사업자등록번호 / 대표자명 / 사업장주소 / 전화번호).
	// English visitors get the translated value when one has been entered,
	// falling back to the default so the details are never missing. Fields left
	// blank in the admin settings are omitted rather than shown empty.
	let businessInfo = $derived.by(() => {
		const b = data.business_settings;
		if (!b) return [];
		const localized = (value, valueEn) =>
			(currentLanguage === 'en' && valueEn) ? valueEn : value;
		return [
			[m.footer_businessName(), localized(b.business_name, b.business_name_en)],
			[m.footer_representative(), localized(b.representative, b.representative_en)],
			[m.footer_businessRegistrationNumber(), b.business_registration_number],
			[m.footer_businessAddress(), localized(b.address, b.address_en)],
			[m.footer_businessPhone(), b.phone],
		].filter(([, value]) => value);
	});
</script>

<svelte:head>
	<title>{data.site_settings?.site_name ?? 'IEUM'}</title>
	{#if data.site_settings?.site_description}
		<meta name="description" content={data.site_settings.site_description} />
		<meta property="og:description" content={data.site_settings.site_description} />
		<meta property="twitter:description" content={data.site_settings.site_description} />
	{/if}
	{#if data.site_settings?.site_keywords}
		<meta name="keywords" content={data.site_settings.site_keywords} />
	{/if}
	<meta property="og:type" content="website" />
	<meta property="og:title" content={data.site_settings?.site_name ?? 'IEUM'} />
	<meta property="og:site_name" content={data.site_settings?.site_name ?? 'IEUM'} />
	<meta property="twitter:card" content="summary_large_image" />
	<meta property="twitter:title" content={data.site_settings?.site_name ?? 'IEUM'} />
	<meta property="og:image" content="{$page.url.origin}/og-image?url={encodeURIComponent($page.url.href)}" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta property="twitter:image" content="{$page.url.origin}/og-image?url={encodeURIComponent($page.url.href)}" />
</svelte:head>

{#if isLoading}
	<div class="fixed inset-0 bg-white flex items-center justify-center z-50">
		<Spinner size="12" />
	</div>
{:else}
	{#key currentLanguage}
	<div class={isReceiptPage ? '' : 'flex min-h-screen flex-col bg-slate-50'}>
{#if !isReceiptPage}
<Navbar class="border-b border-gray-200 bg-white py-2">
	<div class="container mx-auto flex items-center justify-between px-4">
		<!-- Logo -->
		<NavBrand href="/" class="flex items-center">
			<img src="/logo.webp" class="h-10 sm:h-12" alt="Logo" />
		</NavBrand>

		<!-- Right side: Language selector and Auth buttons -->
		<div class="flex flex-row items-center gap-3">
			<!-- Language Selector -->
			<Button color="none" size="sm" class="flex items-center gap-1 hover:bg-gray-100">
				<Globe class="w-5 h-5" />
				<span class="text-sm font-medium">{currentLanguage.toUpperCase()}</span>
			</Button>
			<Dropdown simple bind:open={languageDropdownOpen}>
				{#each languages as lang}
					<DropdownItem onclick={() => { switchLanguage(lang.code); languageDropdownOpen = false; }}>
						{lang.name}
					</DropdownItem>
				{/each}
			</Dropdown>

			{#if data.user}
				<!-- User Profile Dropdown -->
				<Avatar size="sm" class="cursor-pointer">
					{data.user.first_name.charAt(0)}{data.user.last_name.charAt(0)}
				</Avatar>
				<Dropdown simple placement="bottom-end" bind:open={profileDropdownOpen}>
					<DropdownHeader>
						<span class="block text-sm font-semibold">{data.user.first_name} {data.user.last_name}</span>
						<span class="block truncate text-sm text-gray-500">{data.user.email}</span>
					</DropdownHeader>
					<DropdownItem href="/profile" onclick={() => profileDropdownOpen = false}>{m.nav_myProfile()}</DropdownItem>
					<DropdownDivider />
					<DropdownItem href="/registration-history" onclick={() => profileDropdownOpen = false}>{m.nav_registrationHistory()}</DropdownItem>
					<DropdownItem href="/payment-history" onclick={() => profileDropdownOpen = false}>{m.nav_paymentHistory()}</DropdownItem>
					{#if data.user.is_staff}
						<DropdownDivider />
						<DropdownItem href="/{data.admin_page_name}" onclick={() => profileDropdownOpen = false}>{m.nav_adminPage()}</DropdownItem>
					{/if}
					<DropdownDivider />
					<DropdownItem href="/logout" data-sveltekit-reload onclick={() => profileDropdownOpen = false}>{m.nav_signOut()}</DropdownItem>
				</Dropdown>
			{:else}
				<!-- Login Button -->
				<Button
					href="/login?next={encodeURIComponent(nextPath)}"
					color="primary"
					size="sm"
				>
					{m.nav_login()}
				</Button>
			{/if}
		</div>
	</div>
</Navbar>
{/if}

{@render children()}

<CookieConsent />

<div class="flex-1"></div>

{#if !isReceiptPage}
<footer class="mt-16 bg-white">
	<div class="container mx-auto px-4 py-10 sm:px-7">
		<div class="grid gap-x-8 gap-y-10 md:grid-cols-12">
			<!-- Brand: carries the copyright so the column reads as a block, not a gap -->
			<div class="md:col-span-4">
				<a href="/" class="inline-block">
					<img
						src="/logo.webp"
						class="h-10 w-auto opacity-90 transition-opacity hover:opacity-100"
						alt="Logo"
					/>
				</a>
				<p class="mt-4 text-xs leading-relaxed text-gray-400">
					© {new Date().getFullYear()} {m.footer_copyright()}<br />
					Powered by
					<a
						href="https://github.com/pjb7687/ieum"
						target="_blank"
						rel="noopener noreferrer"
						class="underline-offset-4 transition-colors hover:text-gray-700 hover:underline"
					>IEUM</a>
				</p>
			</div>

			<!-- Legal -->
			<div class="md:col-span-3">
				<h2 class="text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-gray-400">
					{m.footer_legal()}
				</h2>
				<ul class="mt-3 space-y-2 text-sm">
					<li>
						<a href="/privacy-policy" class="text-gray-600 transition-colors hover:text-gray-900">
							{m.footer_privacyPolicy()}
						</a>
					</li>
					<li>
						<a href="/terms-of-service" class="text-gray-600 transition-colors hover:text-gray-900">
							{m.footer_termsOfService()}
						</a>
					</li>
				</ul>
			</div>

			<!-- Business registration details (published as text for card issuer review) -->
			{#if businessInfo.length > 0}
				<div class="md:col-span-5">
					<h2 class="text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-gray-400">
						{m.footer_businessInfo()}
					</h2>
					<address class="mt-3 not-italic">
						<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
							{#each businessInfo as [label, value]}
								<dt class="text-gray-400">{label}</dt>
								<dd class="text-gray-700">{value}</dd>
							{/each}
						</dl>
					</address>
				</div>
			{/if}
		</div>
	</div>
</footer>
{/if}
	</div>
	{/key}
{/if}
