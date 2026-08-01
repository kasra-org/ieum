<script>
    import { invalidateAll } from '$app/navigation';
    import { browser } from '$app/environment';
    import { Heading, Button, Input, Textarea, Alert, Card, Checkbox } from '$lib/components/ui';

    let { data } = $props();

    // DOMPurify for XSS protection
    let DOMPurify = $state(null);
    $effect(() => {
        if (browser && !DOMPurify) {
            import('dompurify').then(module => {
                DOMPurify = module.default;
            });
        }
    });
    function sanitizeHtml(html) {
        if (!html) return '';
        if (browser && DOMPurify) {
            return DOMPurify.sanitize(html);
        }
        // DOMPurify is browser-only; never hand back unsanitized markup.
        return '';
    }

    let max_votes = data.event.max_votes;
    let voted_abstracts = $state([]);

    let error_message = $state('');
    const submitVotes = async () => {
        const body = new FormData();
        body.append('voted_abstracts', voted_abstracts.join(','));
        const response = await fetch(`?/submit_votes`, {
            method: 'POST',
            body
        });
        if (response.ok) {
            invalidateAll();
        } else {
            const data = await response.json();
            error_message = data.message;
        }
    };
</script>

<svelte:head>
    <title>Abstract Voting - {data.event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<Heading tag="h1" class="text-2xl font-bold mb-3">Abstract Voting</Heading>
<p class="mb-6">Please review the abstract below and vote for the ones you think are the best.</p>

{#if data.vote.voted_abstracts.length > 0}
    <p class="mt-12 mb-6 text-center">You have already voted for this event.</p>
    <div class="flex justify-center">
        <Button href={`/event/${data.event.id}`} class="mt-6" size="lg" color="primary">Go Back</Button>
    </div>
{:else}
    {#if data.abstracts.length === 0}
    <Alert type="info" class="mb-6">No abstracts to review.</Alert>
    {:else}
    <Alert type="info" class="mb-6">You can vote up to {max_votes} abstracts (remaining votes: {max_votes - voted_abstracts.length})</Alert>
    {/if}

    {#each data.abstracts as abstract}
    <Card size="xl" class="text-black mt-6">
        <div class="text-center">
            <h3 class="text-lg font-bold">{abstract.title}</h3>
            <p class="text-sm text-gray-600 mb-6">Presented by {abstract.attendee.name}</p>
        </div>
        <hr class="mb-5 border-gray-200" />
        {@html sanitizeHtml(abstract?.body)}
        <hr class="mb-5 border-gray-200" />
        <div class="flex justify-center gap-2">
            <Checkbox onclick={(e) => {
                if (e.target.checked) {
                    if (!voted_abstracts.includes(abstract.id) && voted_abstracts.length < max_votes) {
                        voted_abstracts = [...voted_abstracts, abstract.id];
                    }
                } else {
                    voted_abstracts = voted_abstracts.filter((id) => id !== abstract.id);
                }
            }} value={voted_abstracts.includes(abstract.id)}>Vote to this abstract</Checkbox>
        </div>
    </Card>
    {/each}

    {#if error_message}
    <Alert color="red" class="mt-6">{error_message}</Alert>
    {/if}

    <div class="flex justify-center gap-5">
        <Button size="lg" class="mt-6" onclick={submitVotes} disabled={voted_abstracts.length === 0}>Submit Votes</Button>
        <Button href={`/event/${data.event.id}`} class="mt-6" size="lg" color="alternative">Go Back</Button>
    </div>
{/if}