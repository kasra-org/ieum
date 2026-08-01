<script>
    import { enhance } from '$app/forms';
    import { Alert, Button, Card, Heading, Input, Label, Li, List, Select, Textarea } from '$lib/components/ui';
    import { ChevronDown, ChevronUp } from '@lucide/svelte';
    import { flip } from 'svelte/animate';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    let custom_questions = $state({});
    let message_custom_question_changes = $state({});
    let nextKey = 1;

    function moveQuestion(index, direction) {
        const newIndex = index + direction;
        if (newIndex < 0 || newIndex >= custom_questions.length) return;
        const updated = [...custom_questions];
        [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
        custom_questions = updated;
    }

    const addNewCustomQuestion = () => {
        custom_questions = [...custom_questions, {
            id: -1,
            _key: nextKey++,
            question: {
                type: 'checkbox',
                question: '',
                options: ''
            }
        }];
        scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    };

    const resetCustomQuestionChanges = () => {
        custom_questions = data.questions.map(q => {
            let rtn = {
                id: q.id,
                _key: nextKey++,
                question: {
                    type: q.question.type,
                    question: q.question.question
                }
            };
            if (q.question.options) {
                rtn.question.options = q.question.options.join('\n');
            }
            return rtn;
        });
    };

    const afterSuccessfulSubmitCustomQuestionChanges = () => {
        return async ({ result, action, update }) => {
            if (action.search.includes('update_questions')) {
                if (result.type === 'success') {
                    await update({ reset: false });
                    resetCustomQuestionChanges();
                    message_custom_question_changes = { type: 'success', message: m.eventQuestions_successMessage() };
                } else {
                    message_custom_question_changes = { type: 'error', message: m.eventQuestions_errorMessage() };
                }
            }
            scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
        };
    };

    $effect.pre(() => {
        resetCustomQuestionChanges();
    });
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.eventQuestions_title()}</Heading>
<p class="font-light mb-6">{m.eventQuestions_description()}</p>
<List class="mb-6">
    <Li>{m.eventQuestions_defaultInfo()}</Li>
</List>
<p class="font-light mb-6">{m.eventQuestions_supportedTypes()}</p>
<form method="POST" action="?/update_questions" use:enhance={afterSuccessfulSubmitCustomQuestionChanges}>
    <div class="flex justify-center mb-6 gap-2">
        <Button color="primary" onclick={resetCustomQuestionChanges}>{m.eventQuestions_resetChanges()}</Button>
        <Button type="submit" color="primary">{m.eventQuestions_applyChanges()}</Button>
    </div>
    {#each custom_questions as question, i (question._key)}
    <div animate:flip={{ duration: 300 }}>
    <Card size="xl" class="mb-6 p-5">
        <div class="flex justify-between items-center mb-4">
            <span class="text-sm font-medium text-gray-500">#{i + 1}</span>
            <div class="flex gap-1">
                <Button type="button" size="xs" color="light" disabled={i === 0} onclick={() => moveQuestion(i, -1)}>
                    <ChevronUp class="w-4 h-4" />
                </Button>
                <Button type="button" size="xs" color="light" disabled={i === custom_questions.length - 1} onclick={() => moveQuestion(i, 1)}>
                    <ChevronDown class="w-4 h-4" />
                </Button>
            </div>
        </div>
        <div class="mb-6">
            <Label for="question_type" class="block mb-2">{m.eventQuestions_questionType()}</Label>
            <Select id="question_type" name="question_type[]" bind:value={question.question.type} items={[
                { value: 'checkbox', name: m.questionType_checkbox() },
                { value: 'select', name: m.questionType_select() },
                { value: 'text', name: m.questionType_text() },
                { value: 'textarea', name: m.questionType_textarea() }
            ]} />
        </div>
        <div class="mb-6">
            <Label for="question_question" class="block mb-2">{m.eventQuestions_question()}</Label>
            <Textarea id="question_question" name="question_question[]" bind:value={question.question.question} class="w-full" />
        </div>
        {#if question.question.type === 'checkbox' || question.question.type === 'select'}
        <div class="mb-6">
            <Label for="question_options" class="block mb-2">{m.eventQuestions_options()}</Label>
            <Textarea id="question_options" name="question_options[]" rows="3" bind:value={question.question.options} class="w-full" />
        </div>
        {/if}
        <Input type="hidden" name="question_id[]" bind:value={question.id} />
        <div class="flex justify-center">
            <Button color="red" class="ml-2" onclick={() => {
                custom_questions = custom_questions.filter((_, idx) => idx !== i);
            }}>{m.eventQuestions_deleteQuestion()}</Button>
        </div>

    </Card>
    </div>
    {/each}
    {#if custom_questions.length === 0}
        <p class="font-light text-center mb-6">{m.eventQuestions_noQuestions()}</p>
    {/if}
    <div class="flex justify-center mb-6">
        <Button color="dark" onclick={addNewCustomQuestion}>+</Button>
    </div>
    <div class="mb-6">
        {#if message_custom_question_changes.type === 'success'}
            <Alert type="success" color="green">{message_custom_question_changes.message}</Alert>
        {:else if message_custom_question_changes.type === 'error'}
            <Alert type="error" color="red">{message_custom_question_changes.message}</Alert>
        {/if}
    </div>
    <div class="flex justify-center gap-2">
        <Button color="primary" onclick={resetCustomQuestionChanges}>{m.eventQuestions_resetChanges()}</Button>
        <Button type="submit" color="primary">{m.eventQuestions_applyChanges()}</Button>
    </div>
</form>
