<script>
    import { Alert, Button, Heading } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    import EventAdminForm from '$lib/components/event_admin/EventAdminForm.svelte';

    let { data = {} } = $props();

    let success = $state("");
    let failure = $state("");
    let eventFormData = $state(data.event);

    // Update form data when server data changes
    $effect(() => {
        eventFormData = data.event;
    });

    const afterSubmit = () => {
        return async ({ result, action, update }) => {
            console.log(result);
            if (result.type === "success") {
                success = result.data.message;
                failure = "";
            } else {
                failure = result.error.message;
                success = "";
            }
        }
    };

    function handleSubmit(event) {
        // Validate main_languages before submission
        if (!eventFormData.main_languages || eventFormData.main_languages.length === 0) {
            event.preventDefault();
            failure = m.eventForm_mainLanguagesRequired();
            success = "";
            // Scroll to the error message
            const errorElement = document.querySelector('.text-red-600');
            if (errorElement) {
                errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return false;
        }
        // Clear any previous error messages
        failure = "";
        success = "";
    }
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.eventInfo_title()}</Heading>
<p class="font-light mb-6">{m.eventInfo_description()}</p>
<form method="POST" action="?/update_event" use:enhance={afterSubmit} onsubmit={handleSubmit}>
    <EventAdminForm bind:data={eventFormData} />
    <div class="mb-6">
        {#if success}
            <Alert color="green">{success}</Alert>
        {/if}
        {#if failure}
            <Alert color="red">{failure}</Alert>
        {/if}
    </div>
    <div class="flex justify-center">
        <Button color="primary" type="submit" size="lg">{m.eventInfo_update()}</Button>
    </div>
</form>