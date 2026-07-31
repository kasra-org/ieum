<script>
    import { Card, Button } from 'flowbite-svelte';
    import { Sidebar, SidebarGroup, SidebarItem, SidebarWrapper } from 'flowbite-svelte';
    import { CalendarMonthSolid, UsersGroupSolid, BuildingSolid, CogSolid, ClockSolid, FileLinesSolid, ClipboardListSolid, GlobeSolid, KeySolid } from 'flowbite-svelte-icons';
    import { onMount } from 'svelte';
    import { fly } from 'svelte/transition';
    import * as m from '$lib/paraglide/messages.js';

    import Events from '$lib/components/admin/Events.svelte';
    import Users from '$lib/components/admin/Users.svelte';
    import Institutions from '$lib/components/admin/Institutions.svelte';
    import BusinessSettings from '$lib/components/admin/BusinessSettings.svelte';
    import AccountSettings from '$lib/components/admin/AccountSettings.svelte';
    import PrivacyPolicy from '$lib/components/admin/PrivacyPolicy.svelte';
    import TermsOfService from '$lib/components/admin/TermsOfService.svelte';
    import SiteSettings from '$lib/components/admin/SiteSettings.svelte';
    import ApiKeys from '$lib/components/admin/ApiKeys.svelte';

    let { data } = $props();

    let sidebar_selected = $state('events');
    const setAdminPage = () => {
        if (!location.hash) {
            sidebar_selected = 'events';
            return;
        }
        if (location.hash !== '#events' &&
            location.hash !== '#users' &&
            location.hash !== '#institutions' &&
            location.hash !== '#site_settings' &&
            location.hash !== '#business_settings' &&
            location.hash !== '#account_settings' &&
            location.hash !== '#privacy_policy' &&
            location.hash !== '#terms_of_service'
        ) {
            location.hash = '#events';
            return;
        }
        sidebar_selected = location.hash.slice(1);
        const el = document.getElementById('scroll_here');
        if (el) {
            el.scrollIntoView({ behavior: 'smooth' });
        }
    };

    // Initialize sidebar state based on screen size
    let isSidebarOpen = $state(typeof window !== 'undefined' ? window.innerWidth >= 768 : true);
    let wasLargeScreen = $state(typeof window !== 'undefined' ? window.innerWidth >= 768 : true);

    function toggleSidebar() {
        isSidebarOpen = !isSidebarOpen;
    }

    function handleResize() {
        if (typeof window === 'undefined') return;

        const isLargeScreen = window.innerWidth >= 768;

        // Only auto-hide/show when crossing the breakpoint
        if (wasLargeScreen !== isLargeScreen) {
            isSidebarOpen = isLargeScreen;
            wasLargeScreen = isLargeScreen;
        }
    }

    onMount(() => {
        // Set initial state based on screen size
        const isLargeScreen = window.innerWidth >= 768;
        isSidebarOpen = isLargeScreen;
        wasLargeScreen = isLargeScreen;

        // Add resize listener
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
        };
    });

    $effect.pre(() => {
        setAdminPage();
    });
</script>

<svelte:head>
    <title>{m.admin_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<svelte:window onhashchange={setAdminPage}/>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-4 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.admin_title()}</h1>
        <p class="text-slate-200 mt-2">{m.admin_description()}</p>
    </div>
</div>

<div id="scroll_here">&nbsp;</div>

<Card size="xl" class="!p-0">
    <div class="flex flex-row items-stretch relative">
        {#if isSidebarOpen}
            <div class="relative -mr-70 md:mr-0 border-r border-gray-300 bg-gray-50 z-40 md:z-auto" transition:fly={{ x: -100, duration: 300 }}>
                <Sidebar alwaysOpen={true} backdrop={false} class="sticky top-0 py-2 w-70 max-h-screen" activeClass="bg-primary-100 text-primary-900 hover:bg-primary-200" nonActiveClass="hover:bg-gray-100">
                    <Button class="text-md absolute top-32 right-0 translate-x-1/2 bg-gray-50 border border-gray-300 z-50" size="xs" color="none" onclick={toggleSidebar}>
                        &lsaquo;
                    </Button>
                    <div class="overflow-y-auto max-h-screen">
                    <SidebarGroup>
                        <SidebarItem label={m.admin_sidebar_events()} active={sidebar_selected === 'events'} href="#events">
                            {#snippet icon()}
                                <CalendarMonthSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_users()} active={sidebar_selected === 'users'} href="#users">
                            {#snippet icon()}
                                <UsersGroupSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_institutions()} active={sidebar_selected === 'institutions'} href="#institutions">
                            {#snippet icon()}
                                <BuildingSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_siteSettings()} active={sidebar_selected === 'site_settings'} href="#site_settings">
                            {#snippet icon()}
                                <GlobeSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_businessSettings()} active={sidebar_selected === 'business_settings'} href="#business_settings">
                            {#snippet icon()}
                                <CogSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_accountSettings()} active={sidebar_selected === 'account_settings'} href="#account_settings">
                            {#snippet icon()}
                                <ClockSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_privacyPolicy()} active={sidebar_selected === 'privacy_policy'} href="#privacy_policy">
                            {#snippet icon()}
                                <FileLinesSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        <SidebarItem label={m.admin_sidebar_termsOfService()} active={sidebar_selected === 'terms_of_service'} href="#terms_of_service">
                            {#snippet icon()}
                                <ClipboardListSolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        {#if data.admin.apiKeys}
                        <SidebarItem label={m.admin_sidebar_apiKeys()} active={sidebar_selected === 'api_keys'} href="#api_keys">
                            {#snippet icon()}
                                <KeySolid class="w-6 h-6" />
                            {/snippet}
                        </SidebarItem>
                        {/if}
                    </SidebarGroup>
                    </div>
                </Sidebar>
            </div>
        {:else}
            <div class="relative">
                <div class="sticky top-0">
                    <Button class="text-md absolute top-32 left-0 -translate-x-1/2 bg-gray-50 border border-gray-300 z-50" size="xs" color="none" onclick={toggleSidebar}>
                        &rsaquo;
                    </Button>
                </div>
            </div>
        {/if}
        <div class="p-6 sm:p-8 overflow-auto w-full">
            {#if sidebar_selected === 'events'}
            <Events {data} />
            {/if}

            {#if sidebar_selected === 'api_keys' && data.admin.apiKeys}
            <ApiKeys {data} />
            {/if}

            {#if sidebar_selected === 'users'}
            <Users {data} />
            {/if}

            {#if sidebar_selected === 'institutions'}
            <Institutions {data} />
            {/if}

            {#if sidebar_selected === 'site_settings'}
            <SiteSettings {data} />
            {/if}

            {#if sidebar_selected === 'business_settings'}
            <BusinessSettings {data} />
            {/if}

            {#if sidebar_selected === 'account_settings'}
            <AccountSettings {data} />
            {/if}

            {#if sidebar_selected === 'privacy_policy'}
            <PrivacyPolicy {data} />
            {/if}

            {#if sidebar_selected === 'terms_of_service'}
            <TermsOfService {data} />
            {/if}
        </div>
    </div>
</Card>