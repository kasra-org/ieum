<script>
    import { Button } from '$lib/components/ui';
    import { FileText } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { getPresentationTypeLabel } from '$lib/utils.js';

    let { event, my_abstract, attendee = null } = $props();

    // Matches the API gate on abstract submission: an unpaid registration
    // cannot submit, so point at payment instead of a form that would 400.
    const paymentPending = $derived(attendee?.payment_status === 'pending');
</script>

<div class="flex items-center gap-2 mb-6">
    <FileText class="w-6 h-6 text-gray-700" />
    <h2 class="text-xl font-bold text-gray-900">{m.myRegistration_abstractInfo()}</h2>
</div>

{#if event.accepts_abstract}
    {#if event.abstract_submission_type === 'external' && event.external_abstract_url}
        <div class="pl-8">
            <p class="text-gray-600 mb-4">{m.myRegistration_externalAbstract()}</p>
            <Button color="primary" href={event.external_abstract_url} target="_blank" rel="noopener noreferrer">{m.myRegistration_goToExternalAbstract()}</Button>
        </div>
    {:else if my_abstract}
        <div class="space-y-4 pl-8">
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_abstractTitle()}</p>
                <p class="text-base text-gray-900">{my_abstract.title}</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <p class="text-sm font-medium text-gray-500">{m.myRegistration_abstractType()}</p>
                    <p class="text-base text-gray-900">{getPresentationTypeLabel(my_abstract, m)}</p>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex flex-wrap gap-4 mt-8 pt-6 border-t border-gray-200">
                <Button color="light" href="/event/{event.id}/abstract">{m.eventDetail_viewAbstract()}</Button>
            </div>
        </div>
    {:else}
        <div class="pl-8">
            <p class="text-gray-600 mb-4">{m.myRegistration_noAbstract()}</p>
            {#if paymentPending}
                <p class="text-gray-600 mb-4">{m.abstractSubmission_paymentRequiredDescription()}</p>
                <Button color="primary" href="/event/{event.id}/register">{m.eventRegister_payNow()}</Button>
            {:else}
                <Button color="primary" href="/event/{event.id}/abstract">{m.myRegistration_submitAbstract()}</Button>
            {/if}
        </div>
    {/if}
{:else}
    <div class="pl-8">
        <p class="text-gray-600">{m.myRegistration_noAbstractsAccepted()}</p>
    </div>
{/if}
