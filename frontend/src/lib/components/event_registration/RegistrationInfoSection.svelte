<script>
    import { Button, Checkbox } from '$lib/components/ui';
    import { CircleUser, ClipboardList } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { generateCertificatePDF } from '$lib/pdfUtils.js';

    let { event, attendee } = $props();

    // Check if event has ended (certificate can only be generated after event ends)
    let eventHasEnded = $derived(event?.end_date ? new Date() > new Date(event.end_date) : false);

    // Determine which languages are included in the event
    let hasEnglish = $derived(event.main_languages && event.main_languages.includes('en'));
    let hasKorean = $derived(event.main_languages && event.main_languages.includes('ko'));

    // Display based on event language
    const currentLang = languageTag();
    let showEnglishName = $derived(hasEnglish);
    let showKoreanName = $derived(hasKorean || currentLang === 'ko');

    // Helper to get nationality display text
    function getNationalityText(nationality) {
        switch(nationality) {
            case 1: return m.nationality_korean();
            case 2: return m.nationality_nonKorean();
            default: return m.nationality_notSpecified();
        }
    }

    // Parse checkbox answer format
    function parseCheckboxAnswer(answer) {
        const lines = answer.split(/\r?\n/);
        return lines.map(line => {
            const match = line.trim().match(/^-\s*(.+?):\s*(.+)$/);
            if (match) {
                return {
                    option: match[1].trim(),
                    checked: match[2].trim() === 'on' || match[2].trim() === 'true' || match[2].trim() === 'checked'
                };
            }
            return null;
        }).filter(item => item !== null);
    }

    // Generate certificate PDF
    async function generateCertificate() {
        if (!attendee || !event) return;

        let name = '';
        const nameParts = [attendee.first_name || ''];
        if (attendee.middle_initial) nameParts.push(attendee.middle_initial);
        nameParts.push(attendee.last_name || '');
        name = nameParts.filter(Boolean).join(' ');
        if (attendee.korean_name) {
            name = name ? `${name} (${attendee.korean_name})` : attendee.korean_name;
        }

        const certAttendee = {
            name: name,
            institute: attendee.institute || ''
        };

        const certMessages = {
            certIssueDate: m.attendees_certIssueDate,
            certTitle: m.attendees_certTitle,
            certName: m.attendees_certName,
            certInstitute: m.attendees_certInstitute,
            certHasAttended: m.attendees_certHasAttended,
            certOn: m.attendees_certOn,
            certHeldAt: m.attendees_certHeldAt,
            certAsParticipant: m.attendees_certAsParticipant,
            certFooter: m.attendees_certFooter
        };

        const pdfUri = await generateCertificatePDF({
            attendee: certAttendee,
            event: event,
            messages: certMessages
        });

        window.open(pdfUri, '_blank');
    }
</script>

<div class="mb-8">
    <div class="flex items-center gap-2 mb-6">
        <CircleUser class="w-6 h-6 text-gray-700" />
        <h2 class="text-xl font-bold text-gray-900">{m.myRegistration_personalInfo()}</h2>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pl-8">
        {#if showEnglishName}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_firstName()}</p>
                <p class="text-base text-gray-900">{attendee.first_name}</p>
            </div>
            {#if attendee.middle_initial}
                <div>
                    <p class="text-sm font-medium text-gray-500">{m.form_middleInitial()}</p>
                    <p class="text-base text-gray-900">{attendee.middle_initial}</p>
                </div>
            {/if}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_lastName()}</p>
                <p class="text-base text-gray-900">{attendee.last_name}</p>
            </div>
        {/if}
        {#if showKoreanName && attendee.korean_name}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_koreanName()}</p>
                <p class="text-base text-gray-900">{attendee.korean_name}</p>
            </div>
        {/if}
        <div>
            <p class="text-sm font-medium text-gray-500">{m.form_nationality()}</p>
            <p class="text-base text-gray-900">{getNationalityText(attendee.nationality)}</p>
        </div>
        <div>
            <p class="text-sm font-medium text-gray-500">{m.form_institute()}</p>
            <p class="text-base text-gray-900">{currentLang === 'ko' && attendee.institute_ko ? attendee.institute_ko : attendee.institute}</p>
        </div>
        {#if attendee.department}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_department()}</p>
                <p class="text-base text-gray-900">{attendee.department}</p>
            </div>
        {/if}
        {#if attendee.job_title}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_jobTitle()}</p>
                <p class="text-base text-gray-900">{attendee.job_title}</p>
            </div>
        {/if}
        {#if attendee.disability}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_disability()}</p>
                <p class="text-base text-gray-900">{attendee.disability}</p>
            </div>
        {/if}
        {#if attendee.dietary}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.form_dietary()}</p>
                <p class="text-base text-gray-900">{attendee.dietary}</p>
            </div>
        {/if}
    </div>
</div>

<!-- Event-Specific Answers Section -->
{#if attendee.custom_answers && attendee.custom_answers.length > 0}
    <div class="pt-6 border-t border-gray-200">
        <div class="flex items-center gap-2 mb-4">
            <ClipboardList class="w-6 h-6 text-gray-700" />
            <h2 class="text-xl font-bold text-gray-900">{m.myRegistration_eventSpecificAnswers()}</h2>
        </div>
        <div class="space-y-4 pl-8">
            {#each attendee.custom_answers as answer}
                <div>
                    <p class="text-sm font-medium text-gray-500 mb-2">{answer.question}</p>
                    {#if answer.reference?.question?.type === 'checkbox'}
                        <div class="space-y-2">
                            {#each parseCheckboxAnswer(answer.answer) as item}
                                <Checkbox checked={item.checked} disabled>{item.option}</Checkbox>
                            {/each}
                        </div>
                    {:else}
                        <p class="text-base text-gray-900">{answer.answer}</p>
                    {/if}
                </div>
            {/each}
        </div>
    </div>
{/if}

<!-- Print Certificate Button -->
<div class="flex flex-wrap gap-4 mt-8 pt-6 border-t border-gray-200">
    <Button color="light" disabled={!eventHasEnded || !attendee?.is_attended} onclick={generateCertificate}>{m.paymentHistory_printCertificate()}</Button>
</div>
