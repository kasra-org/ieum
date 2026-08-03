<script>
    import { Button, Alert, Card } from '$lib/components/ui';
    import { Sidebar, SidebarGroup, SidebarItem } from '$lib/components/ui';
    import { CircleUser, CreditCard, FileText } from '@lucide/svelte';
    import { onMount } from 'svelte';
    import { fly } from 'svelte/transition';
    import * as m from '$lib/paraglide/messages.js';
    import ChangeRequestModal from '$lib/components/ChangeRequestModal.svelte';
    import RegistrationInfoSection from '$lib/components/event_registration/RegistrationInfoSection.svelte';
    import AbstractInfoSection from '$lib/components/event_registration/AbstractInfoSection.svelte';
    import PaymentInfoSection from '$lib/components/event_registration/PaymentInfoSection.svelte';

    let { data } = $props();
    let event = $derived(data.event);
    let attendee = $derived(data.attendee);
    let my_abstract = $derived(data.my_abstract);
    let payment = $derived(data.payment);

    // Sidebar state
    let sidebar_selected = $state('registration_info');
    const setPage = () => {
        if (!location.hash) {
            sidebar_selected = 'registration_info';
            return;
        }
        const validHashes = ['#registration_info', '#abstract_info', '#payment_info'];
        if (!validHashes.includes(location.hash)) {
            location.hash = '#registration_info';
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
        if (wasLargeScreen !== isLargeScreen) {
            isSidebarOpen = isLargeScreen;
            wasLargeScreen = isLargeScreen;
        }
    }

    onMount(() => {
        const isLargeScreen = window.innerWidth >= 768;
        isSidebarOpen = isLargeScreen;
        wasLargeScreen = isLargeScreen;
        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    });

    $effect.pre(() => {
        setPage();
    });

    // Change request modal state
    let showChangeRequestModal = $state(false);
</script>

<svelte:head>
    <title>{m.myRegistration_title()} - {event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<svelte:window onhashchange={setPage}/>

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-4 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{m.myRegistration_title()}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/" class="hover:underline">{m.eventDetail_breadcrumbEvents()}</a>
                <span class="mx-2">/</span>
                <a href="/event/{event.id}" class="hover:underline">{event.name}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">{m.myRegistration_title()}</span>
            </p>
        </div>
    </div>

    <div id="scroll_here">&nbsp;</div>

    {#if attendee}
        <Card size="xl" class="!p-0">
            <div class="flex flex-row items-stretch relative">
                {#if isSidebarOpen}
                    <div class="relative -mr-70 md:mr-0 border-r border-gray-300 bg-gray-50 z-40 md:z-auto" transition:fly={{ x: -100, duration: 300 }}>
                        <Sidebar alwaysOpen={true} backdrop={false} class="sticky top-0 py-2 w-70 max-h-screen" classes={{ active: "bg-primary-100 text-primary-900 hover:bg-primary-200", nonactive: "hover:bg-gray-100" }}>
                            <Button class="text-md absolute top-18 right-0 translate-x-1/2 bg-gray-50 border border-gray-300 z-50 px-1" size="xs" color="none" onclick={toggleSidebar}>
                                &lsaquo;
                            </Button>
                            <div class="overflow-y-auto max-h-screen">
                            <SidebarGroup>
                                <SidebarItem label={m.myRegistration_registrationInfo()} active={sidebar_selected === 'registration_info'} href="#registration_info">
                                    {#snippet icon()}
                                        <CircleUser class="w-6 h-6" />
                                    {/snippet}
                                </SidebarItem>
                                <SidebarItem label={m.myRegistration_abstractInfo()} active={sidebar_selected === 'abstract_info'} href="#abstract_info">
                                    {#snippet icon()}
                                        <FileText class="w-6 h-6" />
                                    {/snippet}
                                </SidebarItem>
                                <SidebarItem label={m.myRegistration_paymentInfo()} active={sidebar_selected === 'payment_info'} href="#payment_info">
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
                            <Button class="text-md absolute top-18 left-0 -translate-x-1/2 bg-gray-50 border border-gray-300 z-50 px-1" size="xs" color="none" onclick={toggleSidebar}>
                                &rsaquo;
                            </Button>
                        </div>
                    </div>
                {/if}

                <div class="p-6 sm:p-8 overflow-auto w-full">
                    {#if sidebar_selected === 'registration_info'}
                        <RegistrationInfoSection {event} {attendee} />
                    {/if}

                    {#if sidebar_selected === 'abstract_info'}
                        <AbstractInfoSection {event} {my_abstract} />
                    {/if}

                    {#if sidebar_selected === 'payment_info'}
                        <PaymentInfoSection {payment} {attendee} {event} />
                    {/if}
                </div>
            </div>
        </Card>

        <!-- Action Buttons -->
        <div class="flex justify-center gap-4 mt-8">
            <Button color="light" size="lg" onclick={() => history.back()}>{m.common_goBack()}</Button>
            <Button color="light" size="lg" onclick={() => showChangeRequestModal = true}>{m.paymentHistory_requestCancellation()}</Button>
        </div>
    {:else}
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
            <Alert color="red">
                Unable to load registration details. Please try again later.
            </Alert>
        </div>
    {/if}
</div>

<ChangeRequestModal bind:open={showChangeRequestModal} />
