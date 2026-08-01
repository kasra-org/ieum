<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Modal, Button, Alert } from '$lib/components/ui';
    import { UserPen } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';

    let { data } = $props();

    let user_search_term = $state('');
    let filtered_users = $derived(
        data.admin.users.filter((user) => {
            const searchLower = user_search_term.toLowerCase();
            return user.name.toLowerCase().includes(searchLower) ||
                   (user.korean_name && user.korean_name.toLowerCase().includes(searchLower)) ||
                   user.email.toLowerCase().includes(searchLower) ||
                   (user.institute_en && user.institute_en.toLowerCase().includes(searchLower)) ||
                   (user.institute_ko && user.institute_ko.toLowerCase().includes(searchLower));
        })
    );

    let selected_user = $state(null);
    let user_edit_modal = $state(false);
    let user_edit_error = $state('');

    const openUserEditModal = (user) => {
        selected_user = user;
        user_edit_modal = true;
        user_edit_error = '';
    };

    const afterUserEdit = () => {
        return async ({ result, update }) => {
            if (result.type === "success") {
                await update();
                user_edit_modal = false;
                user_edit_error = '';
                selected_user = null;
            } else {
                user_edit_error = result.error?.message || 'An error occurred';
            }
        }
    };
</script>

<h2 class="text-2xl font-bold mb-2">{m.admin_manageUsers_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_manageUsers_description()}</p>

<TableSearch placeholder={m.admin_searchUsers()} bind:inputValue={user_search_term} hoverable={true}>
    <TableHead>
        <TableHeadCell>{m.admin_tableId()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableUserName()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableEmail()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableInstitute()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableJoinDate()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableActiveStatus()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableVerifiedStatus()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.admin_tableActions()}</TableHeadCell>
    </TableHead>
    <TableBody>
        {#each filtered_users as user}
            <TableBodyRow>
                <TableBodyCell>{user.id}</TableBodyCell>
                <TableBodyCell>{getDisplayName(user)}</TableBodyCell>
                <TableBodyCell>{user.email}</TableBodyCell>
                <TableBodyCell>{getDisplayInstitute(user)}</TableBodyCell>
                <TableBodyCell>{new Date(user.date_joined).toLocaleDateString()}</TableBodyCell>
                <TableBodyCell>
                    <form method="post" action="?/toggle_user_active" use:enhance>
                        <input type="hidden" name="user_id" value={user.id} />
                        <Button size="xs" color={user.is_active ? 'green' : 'red'} type="submit" disabled={user.id === data.user.id}>
                            {user.is_active ? m.admin_userActive() : m.admin_userInactive()}
                        </Button>
                    </form>
                </TableBodyCell>
                <TableBodyCell>
                    <form method="post" action="?/toggle_user_verified" use:enhance>
                        <input type="hidden" name="user_id" value={user.id} />
                        <Button size="xs" color={user.email_verified ? 'green' : 'red'} type="submit">
                            {user.email_verified ? m.admin_userVerified() : m.admin_userUnverified()}
                        </Button>
                    </form>
                </TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center">
                        <Button color="none" size="none" onclick={() => openUserEditModal(user)}>
                            <UserPen class="w-5 h-5" />
                        </Button>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filtered_users.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="8" class="text-center">{m.admin_noUsersFound()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<Modal id="user_edit_modal" size="xl" title={m.admin_editUser()} bind:open={user_edit_modal} outsideclose>
    {#if selected_user}
    <form method="post" action="?/update_user" use:enhance={afterUserEdit}>
        <input type="hidden" name="user_id" value={selected_user.id} />
        <RegistrationForm
            data={{
                email: selected_user.email,
                first_name: selected_user.first_name,
                middle_initial: selected_user.middle_initial,
                korean_name: selected_user.korean_name || '',
                last_name: selected_user.last_name,
                nationality: selected_user.nationality ? selected_user.nationality.toString() : '',
                institute: selected_user.institute,
                department: selected_user.department || '',
                job_title: selected_user.job_title || '',
                disability: selected_user.disability || '',
                dietary: selected_user.dietary || '',
                orcid: selected_user.orcid || ''
            }}
            errors={{}}
            config={{
                hide_login_info: true,
                hide_password: true,
                show_english_name: true,
                show_korean_name: true,
                csrf_token: data.csrf_token
            }}
            institution_resolved={selected_user.institute ? {
                id: selected_user.institute,
                name_en: selected_user.institute_en,
                name_ko: selected_user.institute_ko
            } : null}
        />
        {#if user_edit_error}
            <Alert color="red" class="mb-6">{user_edit_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2 mt-6">
            <Button color="primary" type="submit">{m.admin_update()}</Button>
            <Button color="alternative" type="button" onclick={() => user_edit_modal = false}>{m.common_cancel()}</Button>
        </div>
    </form>
    {/if}
</Modal>
