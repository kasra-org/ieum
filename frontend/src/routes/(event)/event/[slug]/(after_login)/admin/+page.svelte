<script>
    import { error } from '@sveltejs/kit';
    import { Modal, Heading, Button, Table, TableSearch, TableBody, TableBodyCell, TableBodyRow, TableHead, TableHeadCell, Input, Label, Toggle } from '$lib/components/ui';
    import { Card, List, Li, Checkbox, Datepicker, Select } from '$lib/components/ui';
    import { Sidebar, SidebarGroup, SidebarItem, SidebarWrapper, Alert, SidebarButton, uiHelpers } from '$lib/components/ui';
    import { ClipboardList, ContactRound, CreditCard, Eye, EyeOff, Mail, Mic, Newspaper, Pencil, Users } from '@lucide/svelte';
    import { onMount } from 'svelte';
	import { enhance } from '$app/forms';
    import { fly } from 'svelte/transition';
    import { cubicOut } from 'svelte/easing';
    import * as m from '$lib/paraglide/messages.js';

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';
    import EventAdminForm from '$lib/components/event_admin/EventAdminForm.svelte';
    import EventInformation from '$lib/components/event_admin/EventInformation.svelte';
    import EmailTemplates from '$lib/components/event_admin/EmailTemplates.svelte';
    import EventSpecificQuestions from '$lib/components/event_admin/EventSpecificQuestions.svelte';
    import Speakers from '$lib/components/event_admin/Speakers.svelte';
    import Attendees from '$lib/components/event_admin/Attendees.svelte';
    import OnSiteAttendees from '$lib/components/event_admin/OnSiteAttendees.svelte';
    import Abstracts from '$lib/components/event_admin/Abstracts.svelte';
    import EventAdmins from '$lib/components/event_admin/EventAdmins.svelte';
    import Organizers from '$lib/components/event_admin/Organizers.svelte';
    import Transactions from '$lib/components/event_admin/Transactions.svelte';

    let { data } = $props();

    let sidebar_selected = $state('event_information');
    const setAdminPage = () => {
        if (!location.hash) {
            sidebar_selected = 'event_information';
            return;
        }
        if (location.hash !== '#event_information' &&
            location.hash !== '#email_templates' &&
            location.hash !== '#event_specific_questions' &&
            location.hash !== '#speakers' &&
            location.hash !== '#attendees' &&
            location.hash !== '#abstracts' &&
            location.hash !== '#organizers' &&
            location.hash !== '#event_admins' &&
            location.hash !== '#onsite' &&
            location.hash !== '#transactions'
        ) {
            location.hash = '#event_information';
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

    let published = $state(false);
    let saving_published = $state(false);

    // Initialize and update published state from server data
    $effect(() => {
        published = data.event.published;
    });

    $effect.pre(() => {
        setAdminPage();
    });
</script>

<svelte:head>
    <title>{m.admin_title()} - {data.event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<svelte:window onhashchange={setAdminPage}/>

{#snippet process_spaces(text)}
    {@html text.replace(/\n/g, '<br>').replace(/ /g, '&nbsp;')}
{/snippet}

<div class="container mx-auto py-8 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-4 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{data.event.name}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/" class="hover:underline">Events</a>
                <span class="mx-2">/</span>
                <a href="/event/{data.event.id}" class="hover:underline">{data.event.name}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">Admin Panel</span>
            </p>
        </div>
    </div>

    <div id="scroll_here">&nbsp;</div>

    <!-- Published Toggle -->
    <div class="flex justify-end mb-4">
        <form method="POST" action="?/toggle_published" use:enhance={() => {
            saving_published = true;
            return async ({ result, update }) => {
                if (result.type === 'success') {
                    published = !published;
                }
                saving_published = false;
                await update();
            };
        }}>
            <Button type="submit" color={published ? 'green' : 'light'} size="lg" disabled={saving_published}>
                {#if published}
                    <Eye class="w-5 h-5 me-2" />
                    {m.eventPublished_published()}
                {:else}
                    <EyeOff class="w-5 h-5 me-2" />
                    {m.eventPublished_draft()}
                {/if}
            </Button>
        </form>
    </div>

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
                            <SidebarItem label={m.eventAdmin_eventInformation()} active={sidebar_selected === 'event_information'} href="#event_information">
                                {#snippet icon()}
                                    <Newspaper class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_emailTemplates()} active={sidebar_selected === 'email_templates'} href="#email_templates">
                                {#snippet icon()}
                                    <Mail class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_eventSpecificQuestions()} active={sidebar_selected === 'event_specific_questions'} href="#event_specific_questions">
                                {#snippet icon()}
                                    <ClipboardList class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_speakers()} active={sidebar_selected === 'speakers'} href="#speakers">
                                {#snippet icon()}
                                    <Mic class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_attendees()} active={sidebar_selected === 'attendees'} href="#attendees">
                                {#snippet icon()}
                                    <Users class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_onsiteAttendees()} active={sidebar_selected === 'onsite'} href="#onsite">
                                {#snippet icon()}
                                    <Users class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_abstracts()} active={sidebar_selected === 'abstracts'} href="#abstracts">
                                {#snippet icon()}
                                    <Pencil class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_organizers()} active={sidebar_selected === 'organizers'} href="#organizers">
                                {#snippet icon()}
                                    <Users class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_eventAdmins()} active={sidebar_selected === 'event_admins'} href="#event_admins">
                                {#snippet icon()}
                                    <ContactRound class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
                            <SidebarItem label={m.eventAdmin_transactions()} active={sidebar_selected === 'transactions'} href="#transactions">
                                {#snippet icon()}
                                    <CreditCard class="w-6 h-6" />
                                {/snippet}
                            </SidebarItem>
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
                {#if sidebar_selected === 'event_information'}
                <EventInformation data={data} />
                {/if}

                {#if sidebar_selected === 'email_templates'}
                <EmailTemplates data={data} />
                {/if}

                {#if sidebar_selected === 'event_specific_questions'}
                <EventSpecificQuestions data={data} />
                {/if}

                {#if sidebar_selected === 'speakers'}
                <Speakers data={data} />
                {/if}

                {#if sidebar_selected === 'attendees'}
                <Attendees data={data} />
                {/if}

                {#if sidebar_selected === 'onsite'}
                <OnSiteAttendees data={data} />
                {/if}

                {#if sidebar_selected === 'abstracts'}
                <Abstracts data={data} />
                {/if}

                {#if sidebar_selected === 'organizers'}
                <Organizers data={data} />
                {/if}

                {#if sidebar_selected === 'event_admins'}
                <EventAdmins data={data} />
                {/if}

                {#if sidebar_selected === 'transactions'}
                <Transactions data={data} />
                {/if}
            </div>
        </div>
    </Card>
</div>
