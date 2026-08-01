<script>
    import { Table, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Modal, Button, Alert, Label, Input, Select, Badge } from '$lib/components/ui';
    import { RefreshCw, Trash2 } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    let keys = $derived(data.admin.apiKeys ?? []);
    let users = $derived(
        (data.admin.users ?? []).map((u) => ({
            value: u.id,
            name: u.email || u.username
        }))
    );

    let create_modal = $state(false);
    let new_name = $state('');
    let new_user_id = $state(null);

    // Shown once, right after create/rotate — the plaintext is not recoverable.
    let revealed_secret = $state('');
    let error = $state('');

    const userLabel = (id) => {
        const u = (data.admin.users ?? []).find((x) => x.id === id);
        return u ? (u.email || u.username) : `#${id}`;
    };

    const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : m.admin_apiKeys_never());

    /** Shared handler: surface the one-time secret, refresh the list. */
    const afterAction = () => {
        return async ({ result }) => {
            error = '';
            if (result.type === 'success' && result.data?.success) {
                if (result.data.secret) revealed_secret = result.data.secret;
                create_modal = false;
                new_name = '';
                new_user_id = null;
                await invalidateAll();
            } else if (result.type === 'success') {
                error = result.data?.error || 'Request failed';
            }
        };
    };
</script>

<div class="mb-4">
    <h2 class="text-2xl font-bold text-gray-900">{m.admin_apiKeys_title()}</h2>
    <p class="mt-1 text-sm text-gray-500">{m.admin_apiKeys_desc()}</p>
</div>

{#if error}
    <Alert color="red" class="mb-4">{error}</Alert>
{/if}

<div class="mb-4">
    <Button color="primary" onclick={() => { create_modal = true; error = ''; }}>
        {m.admin_apiKeys_create()}
    </Button>
</div>

{#if keys.length === 0}
    <p class="py-8 text-center text-sm text-gray-500">{m.admin_apiKeys_none()}</p>
{:else}
    <Table hoverable={true}>
        <TableHead>
            <TableHeadCell>{m.admin_apiKeys_name()}</TableHeadCell>
            <TableHeadCell>{m.admin_apiKeys_user()}</TableHeadCell>
            <TableHeadCell>{m.admin_apiKeys_prefix()}</TableHeadCell>
            <TableHeadCell>{m.admin_apiKeys_created()}</TableHeadCell>
            <TableHeadCell>{m.admin_apiKeys_lastUsed()}</TableHeadCell>
            <TableHeadCell>{m.admin_apiKeys_status()}</TableHeadCell>
            <TableHeadCell></TableHeadCell>
        </TableHead>
        <TableBody>
            {#each keys as key (key.id)}
                <TableBodyRow>
                    <TableBodyCell>{key.name}</TableBodyCell>
                    <TableBodyCell>{userLabel(key.user_id)}</TableBodyCell>
                    <TableBodyCell><code class="text-xs">{key.prefix}…</code></TableBodyCell>
                    <TableBodyCell>{fmt(key.created_at)}</TableBodyCell>
                    <TableBodyCell>{fmt(key.last_used_at)}</TableBodyCell>
                    <TableBodyCell>
                        {#if key.revoked_at}
                            <Badge color="red">{m.admin_apiKeys_revoked()}</Badge>
                        {:else}
                            <Badge color="green">{m.admin_apiKeys_active()}</Badge>
                        {/if}
                    </TableBodyCell>
                    <TableBodyCell>
                        <div class="flex gap-1">
                            <form method="POST" action="?/rotate_api_key" use:enhance={afterAction}>
                                <input type="hidden" name="key_id" value={key.id} />
                                <Button type="submit" size="xs" color="alternative"
                                        onclick={(e) => { if (!confirm(m.admin_apiKeys_confirmRotate())) e.preventDefault(); }}>
                                    <RefreshCw class="w-3 h-3 me-1" />{m.admin_apiKeys_rotate()}
                                </Button>
                            </form>
                            <form method="POST" action="?/revoke_api_key" use:enhance={afterAction}>
                                <input type="hidden" name="key_id" value={key.id} />
                                <input type="hidden" name="revoked" value={key.revoked_at ? 'false' : 'true'} />
                                <Button type="submit" size="xs" color={key.revoked_at ? 'green' : 'yellow'}>
                                    {key.revoked_at ? m.admin_apiKeys_unrevoke() : m.admin_apiKeys_revoke()}
                                </Button>
                            </form>
                            <form method="POST" action="?/delete_api_key" use:enhance={afterAction}>
                                <input type="hidden" name="key_id" value={key.id} />
                                <Button type="submit" size="xs" color="red"
                                        onclick={(e) => { if (!confirm(m.admin_apiKeys_confirmDelete())) e.preventDefault(); }}>
                                    <Trash2 class="w-3 h-3" />
                                </Button>
                            </form>
                        </div>
                    </TableBodyCell>
                </TableBodyRow>
            {/each}
        </TableBody>
    </Table>
{/if}

<Modal title={m.admin_apiKeys_create()} bind:open={create_modal} size="md" outsideclose>
    <form method="POST" action="?/create_api_key" use:enhance={afterAction} class="space-y-4">
        <div>
            <Label for="key_name" class="mb-2">{m.admin_apiKeys_name()}</Label>
            <Input id="key_name" name="name" bind:value={new_name} required
                   placeholder={m.admin_apiKeys_namePlaceholder()} />
        </div>
        <div>
            <Label for="key_user" class="mb-2">{m.admin_apiKeys_user()}</Label>
            <Select id="key_user" name="user_id" items={users} bind:value={new_user_id} required />
        </div>
        <Button type="submit" color="primary" disabled={!new_name || !new_user_id}>
            {m.admin_apiKeys_create()}
        </Button>
    </form>
</Modal>

<Modal title={m.admin_apiKeys_secretTitle()} open={!!revealed_secret}
       on:close={() => (revealed_secret = '')} size="md" outsideclose>
    <Alert color="yellow">{m.admin_apiKeys_secretWarn()}</Alert>
    <code class="mt-3 block break-all rounded bg-gray-100 p-3 text-sm">{revealed_secret}</code>
    <Button class="mt-3" color="alternative"
            onclick={() => navigator.clipboard?.writeText(revealed_secret)}>Copy</Button>
</Modal>
