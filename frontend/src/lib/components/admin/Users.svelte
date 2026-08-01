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

    // Guest accounts: real login-capable users created by an admin for testing,
    // pre-verified so no inbox round-trip is needed.
    let guest_modal = $state(false);
    let guest_error = $state('');
    let guest_created = $state(null);
    let guest = $state({
        email: '', password: '', first_name: '', last_name: '',
        korean_name: '', job_title: 'Guest', institute: ''
    });

    const openGuestModal = () => {
        guest = { email: '', password: '', first_name: '', last_name: '',
                  korean_name: '', job_title: 'Guest', institute: '' };
        guest_error = '';
        guest_created = null;
        guest_modal = true;
    };

    function suggestGuest() {
        // Distinctive, obviously-disposable defaults so test accounts are easy
        // to spot and never collide with a real signup.
        const stamp = Date.now().toString(36);
        guest.email = `guest+${stamp}@example.com`;
        guest.first_name = 'Guest';
        guest.last_name = stamp.slice(-4).toUpperCase();
        guest.password = crypto.randomUUID().replace(/-/g, '').slice(0, 16);
    }

    const afterGuestCreate = () => {
        return async ({ result, update }) => {
            if (result.type === "success") {
                guest_created = { email: guest.email, password: guest.password };
                guest_error = '';
                await update({ reset: false });
            } else {
                guest_error = result.error?.message || 'An error occurred';
            }
        }
    };

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

<div class="flex justify-end mb-4">
    <Button color="primary" size="sm" onclick={openGuestModal}>{m.admin_guestUser_add()}</Button>
</div>

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
                <TableBodyCell>
                    {getDisplayName(user)}
                    {#if user.is_guest}
                        <span class="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">{m.admin_guestUser_badge()}</span>
                    {/if}
                </TableBodyCell>
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

<Modal id="guest_user_modal" size="lg" title={m.admin_guestUser_title()} bind:open={guest_modal} outsideclose>
    {#if guest_created}
        <!-- Shown once: the password is hashed on save and cannot be read back. -->
        <Alert color="green" class="mb-4">{m.admin_guestUser_created()}</Alert>
        <div class="mb-6 rounded-lg bg-gray-50 p-4 text-sm">
            <div class="flex justify-between py-1">
                <span class="text-gray-600">{m.admin_tableEmail()}</span>
                <span class="font-mono font-medium">{guest_created.email}</span>
            </div>
            <div class="flex justify-between py-1">
                <span class="text-gray-600">{m.admin_guestUser_password()}</span>
                <span class="font-mono font-medium">{guest_created.password}</span>
            </div>
        </div>
        <p class="mb-6 text-sm text-gray-500">{m.admin_guestUser_passwordOnce()}</p>
        <div class="flex justify-center">
            <Button color="primary" onclick={() => (guest_modal = false)}>{m.admin_guestUser_close()}</Button>
        </div>
    {:else}
        <p class="mb-4 text-sm text-gray-600">{m.admin_guestUser_description()}</p>
        <form method="post" action="?/add_guest_user" use:enhance={afterGuestCreate}>
            <div class="mb-4 flex justify-end">
                <Button color="alternative" size="xs" type="button" onclick={suggestGuest}>{m.admin_guestUser_fillSample()}</Button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                    <label for="guest_first_name" class="mb-2 block text-sm font-medium">{m.form_firstName()} <span class="text-red-500">*</span></label>
                    <input id="guest_first_name" name="first_name" type="text" required bind:value={guest.first_name}
                        class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm" />
                </div>
                <div>
                    <label for="guest_last_name" class="mb-2 block text-sm font-medium">{m.form_lastName()} <span class="text-red-500">*</span></label>
                    <input id="guest_last_name" name="last_name" type="text" required bind:value={guest.last_name}
                        class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm" />
                </div>
            </div>
            <div class="mb-4">
                <label for="guest_email" class="mb-2 block text-sm font-medium">{m.admin_tableEmail()} <span class="text-red-500">*</span></label>
                <input id="guest_email" name="email" type="email" required bind:value={guest.email}
                    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm" />
            </div>
            <div class="mb-4">
                <label for="guest_password" class="mb-2 block text-sm font-medium">{m.admin_guestUser_password()} <span class="text-red-500">*</span></label>
                <input id="guest_password" name="password" type="text" required bind:value={guest.password}
                    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 font-mono text-sm" />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                    <label for="guest_job_title" class="mb-2 block text-sm font-medium">{m.form_jobTitle()}</label>
                    <input id="guest_job_title" name="job_title" type="text" bind:value={guest.job_title}
                        class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm" />
                </div>
                <div>
                    <label for="guest_institute" class="mb-2 block text-sm font-medium">{m.form_institute()}</label>
                    <select id="guest_institute" name="institute" bind:value={guest.institute}
                        class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm">
                        <option value="">{m.admin_guestUser_noInstitute()}</option>
                        {#each (data.admin.institutions ?? []) as inst}
                            <option value={inst.id}>{inst.name_en}{inst.name_ko ? ` (${inst.name_ko})` : ''}</option>
                        {/each}
                    </select>
                </div>
            </div>
            {#if guest_error}
                <Alert color="red" class="mb-4">{guest_error}</Alert>
            {/if}
            <div class="flex justify-center gap-2">
                <Button color="primary" type="submit">{m.admin_guestUser_create()}</Button>
                <Button color="alternative" type="button" onclick={() => (guest_modal = false)}>{m.organizers_cancel()}</Button>
            </div>
        </form>
    {/if}
</Modal>

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
