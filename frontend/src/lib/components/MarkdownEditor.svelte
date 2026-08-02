<script>
    import { onMount, onDestroy } from 'svelte';
    import { Editor } from '@tiptap/core';
    import StarterKit from '@tiptap/starter-kit';
    import Image from '@tiptap/extension-image';
    import Link from '@tiptap/extension-link';
    import Placeholder from '@tiptap/extension-placeholder';
    import Underline from '@tiptap/extension-underline';
    import TextAlign from '@tiptap/extension-text-align';
    import { Table } from '@tiptap/extension-table';
    import { TableRow } from '@tiptap/extension-table-row';
    import { TableCell } from '@tiptap/extension-table-cell';
    import { TableHeader } from '@tiptap/extension-table-header';
    import { marked } from 'marked';
    import { Label, Tabs, TabItem, Textarea, Button, Dropdown, DropdownItem, Spinner } from '$lib/components/ui';
    import { Bold, ChevronDown, Columns3, Heading1, Heading2, Heading3,
             Image as ImageIcon, IndentDecrease, IndentIncrease, Italic,
             Link as LinkIcon, List, ListOrdered, Paperclip, Quote,
             Strikethrough, Underline as UnderlineIcon } from '@lucide/svelte';
    import { deserialize } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { value = $bindable(), name = '', id = '', label = '', placeholder = '', rows = 10, required = false } = $props();

    let editor = $state(null);
    let editorElement = $state(null);
    let activeTab = $state('wysiwyg');
    let uploading = $state(false);
    let uploadError = $state('');
    let imageDropdownOpen = $state(false);
    let tableDropdownOpen = $state(false);
    let DOMPurify = $state(null);
    let editorState = $state(0); // Counter to trigger reactivity on editor state changes

    // Configure marked options
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    // Import DOMPurify only on client side
    onMount(async () => {
        const DOMPurifyModule = await import('dompurify');
        DOMPurify = DOMPurifyModule.default;

        initEditor();
    });

    function initEditor() {
        if (!editorElement) return;

        // Convert markdown to HTML for initial content
        let initialHtml = '';
        if (value && DOMPurify) {
            try {
                const rawHtml = marked.parse(value);
                initialHtml = DOMPurify.sanitize(rawHtml);
            } catch (e) {
                console.error('Error parsing initial markdown:', e);
            }
        }

        editor = new Editor({
            element: editorElement,
            extensions: [
                StarterKit.configure({
                    heading: {
                        levels: [1, 2, 3]
                    }
                }),
                Image.configure({
                    inline: true,
                    allowBase64: true,
                }),
                Link.configure({
                    openOnClick: false,
                    HTMLAttributes: {
                        class: 'text-blue-600 underline hover:text-blue-800',
                    },
                }),
                Placeholder.configure({
                    placeholder: placeholder || m.markdownEditor_placeholder(),
                }),
                Underline,
                TextAlign.configure({
                    types: ['heading', 'paragraph'],
                }),
                Table.configure({
                    resizable: true,
                    HTMLAttributes: {
                        class: 'border-collapse border border-gray-300',
                    },
                }),
                TableRow,
                TableHeader.configure({
                    HTMLAttributes: {
                        class: 'border border-gray-300 bg-gray-100 p-2 font-semibold',
                    },
                }),
                TableCell.configure({
                    HTMLAttributes: {
                        class: 'border border-gray-300 p-2',
                    },
                }),
            ],
            content: initialHtml,
            editorProps: {
                attributes: {
                    class: 'prose prose-sm max-w-none focus:outline-none min-h-[200px] p-4',
                },
                handleKeyDown: (view, event) => {
                    if (event.key !== 'Tab') return false;

                    // Tab belongs to the editor. Without this the browser moves
                    // focus to the next form field, so tabbing inside the
                    // description jumped out of it entirely.
                    //
                    // ProseMirror consults editorProps before plugin keymaps, so
                    // returning true here pre-empts TipTap's own Tab bindings -
                    // which is why the list and table behaviour is spelled out
                    // rather than delegated.
                    event.preventDefault();

                    if (editor?.isActive('table')) {
                        editor.commands[event.shiftKey ? 'goToPreviousCell' : 'goToNextCell']();
                    } else if (editor?.isActive('listItem')) {
                        // Fails harmlessly on the first item of a level, which
                        // has no sibling to nest under.
                        editor.commands[event.shiftKey ? 'liftListItem' : 'sinkListItem']('listItem');
                    }
                    return true;
                },
                handleDrop: (view, event, slice, moved) => {
                    if (!moved && event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length > 0) {
                        const file = event.dataTransfer.files[0];
                        if (file.type.startsWith('image/')) {
                            event.preventDefault();
                            handleImageUpload(file, 'inline');
                            return true;
                        }
                    }
                    return false;
                },
                handlePaste: (view, event, slice) => {
                    const items = event.clipboardData?.items;
                    if (items) {
                        for (const item of items) {
                            if (item.type.startsWith('image/')) {
                                event.preventDefault();
                                const file = item.getAsFile();
                                if (file) {
                                    handleImageUpload(file, 'inline');
                                }
                                return true;
                            }
                        }
                    }
                    return false;
                },
            },
            onUpdate: ({ editor }) => {
                // Convert HTML back to markdown for the value
                const html = editor.getHTML();
                value = htmlToMarkdown(html);
            },
            onSelectionUpdate: () => {
                // Trigger reactivity for toolbar button states
                editorState++;
            },
            onTransaction: () => {
                // Trigger reactivity for toolbar button states
                editorState++;
            },
        });
    }

    onDestroy(() => {
        if (editor) {
            editor.destroy();
        }
    });

    /**
     * Serialize a <ul>/<ol> element, and anything nested inside it, to markdown.
     *
     * This cannot be done with regex: a non-greedy /<ul>(.*?)<\/ul>/ match ends
     * at the *inner* list's closing tag, so nesting was flattened - the first
     * sub-item lost its marker entirely and the remaining ones were emitted as
     * top-level items.
     */
    function serializeList(listEl, depth = 0) {
        const ordered = listEl.tagName === 'OL';
        const indent = '  '.repeat(depth);
        const lines = [];
        let index = 1;

        for (const li of Array.from(listEl.children)) {
            if (li.tagName !== 'LI') continue;

            let text = '';
            const sublists = [];
            for (const node of Array.from(li.childNodes)) {
                if (node.nodeType === 1 && (node.tagName === 'UL' || node.tagName === 'OL')) {
                    sublists.push(node);
                } else if (node.nodeType === 1) {
                    // TipTap wraps item content in <p>; unwrap it so items stay
                    // tight rather than becoming blank-line separated.
                    text += node.tagName === 'P' ? node.innerHTML : node.outerHTML;
                } else {
                    text += node.textContent;
                }
            }

            lines.push(`${indent}${ordered ? `${index++}.` : '-'} ${text.trim()}`);
            for (const sub of sublists) lines.push(serializeList(sub, depth + 1));
        }
        return lines.join('\n');
    }

    /** Replace every top-level list block in an HTML string with markdown. */
    function convertLists(html) {
        if (typeof DOMParser === 'undefined') return html;

        let out = '';
        let rest = html;
        while (true) {
            const start = rest.match(/<(ul|ol)\b[^>]*>/i);
            if (!start) { out += rest; break; }
            out += rest.slice(0, start.index);

            // Walk the tags forward tracking depth so we stop at the *matching*
            // close tag rather than the first one.
            const tagRe = /<(\/?)(?:ul|ol)\b[^>]*>/gi;
            tagRe.lastIndex = start.index;
            let depth = 0;
            let endIdx = -1;
            let tag;
            while ((tag = tagRe.exec(rest)) !== null) {
                depth += tag[1] ? -1 : 1;
                if (depth === 0) { endIdx = tag.index + tag[0].length; break; }
            }
            if (endIdx === -1) { out += rest.slice(start.index); break; }

            const block = rest.slice(start.index, endIdx);
            const listEl = new DOMParser()
                .parseFromString(block, 'text/html').body.firstElementChild;
            out += listEl ? `\n${serializeList(listEl, 0)}\n\n` : block;
            rest = rest.slice(endIdx);
        }
        return out;
    }

    // Simple HTML to Markdown converter
    function htmlToMarkdown(html) {
        if (!html || html === '<p></p>') return '';

        let md = html;

        // Convert headings
        md = md.replace(/<h1[^>]*>(.*?)<\/h1>/gi, '# $1\n\n');
        md = md.replace(/<h2[^>]*>(.*?)<\/h2>/gi, '## $1\n\n');
        md = md.replace(/<h3[^>]*>(.*?)<\/h3>/gi, '### $1\n\n');

        // Convert bold and italic
        md = md.replace(/<strong>(.*?)<\/strong>/gi, '**$1**');
        md = md.replace(/<b>(.*?)<\/b>/gi, '**$1**');
        md = md.replace(/<em>(.*?)<\/em>/gi, '*$1*');
        md = md.replace(/<i>(.*?)<\/i>/gi, '*$1*');
        md = md.replace(/<u>(.*?)<\/u>/gi, '<u>$1</u>');

        // Convert links
        md = md.replace(/<a[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '[$2]($1)');

        // Convert images
        md = md.replace(/<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*\/?>/gi, '![$2]($1)');
        md = md.replace(/<img[^>]*src="([^"]*)"[^>]*\/?>/gi, '![]($1)');

        // Convert lists (see convertLists: nesting needs real parsing, not regex)
        md = convertLists(md);

        // Convert blockquotes
        md = md.replace(/<blockquote[^>]*>(.*?)<\/blockquote>/gis, (match, content) => {
            return content.split('\n').map(line => `> ${line}`).join('\n');
        });

        // Convert code
        md = md.replace(/<code>(.*?)<\/code>/gi, '`$1`');
        md = md.replace(/<pre[^>]*><code[^>]*>(.*?)<\/code><\/pre>/gis, '```\n$1\n```');

        // Convert tables
        md = md.replace(/<table[^>]*>(.*?)<\/table>/gis, (match, tableContent) => {
            let rows = [];
            let headerProcessed = false;

            // Process thead
            const theadMatch = tableContent.match(/<thead[^>]*>(.*?)<\/thead>/is);
            if (theadMatch) {
                const headerRow = theadMatch[1].match(/<tr[^>]*>(.*?)<\/tr>/is);
                if (headerRow) {
                    const cells = headerRow[1].match(/<th[^>]*>(.*?)<\/th>/gi) || [];
                    const headerCells = cells.map(cell => {
                        const content = cell.replace(/<th[^>]*>(.*?)<\/th>/i, '$1').replace(/<[^>]+>/g, '').trim();
                        return content;
                    });
                    if (headerCells.length > 0) {
                        rows.push('| ' + headerCells.join(' | ') + ' |');
                        rows.push('| ' + headerCells.map(() => '---').join(' | ') + ' |');
                        headerProcessed = true;
                    }
                }
            }

            // Process tbody or direct tr elements
            const tbodyMatch = tableContent.match(/<tbody[^>]*>(.*?)<\/tbody>/is);
            const bodyContent = tbodyMatch ? tbodyMatch[1] : tableContent;
            const trMatches = bodyContent.match(/<tr[^>]*>(.*?)<\/tr>/gis) || [];

            trMatches.forEach((tr, idx) => {
                // Check if this row has th (header) or td (data) cells
                const thCells = tr.match(/<th[^>]*>(.*?)<\/th>/gi);
                const tdCells = tr.match(/<td[^>]*>(.*?)<\/td>/gi);

                if (thCells && !headerProcessed) {
                    const headerCells = thCells.map(cell => {
                        return cell.replace(/<th[^>]*>(.*?)<\/th>/i, '$1').replace(/<[^>]+>/g, '').trim();
                    });
                    rows.push('| ' + headerCells.join(' | ') + ' |');
                    rows.push('| ' + headerCells.map(() => '---').join(' | ') + ' |');
                    headerProcessed = true;
                } else if (tdCells) {
                    const dataCells = tdCells.map(cell => {
                        return cell.replace(/<td[^>]*>(.*?)<\/td>/i, '$1').replace(/<[^>]+>/g, '').trim();
                    });
                    rows.push('| ' + dataCells.join(' | ') + ' |');
                }
            });

            return rows.length > 0 ? '\n' + rows.join('\n') + '\n\n' : '';
        });

        // Convert paragraphs and line breaks
        md = md.replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n\n');
        md = md.replace(/<br\s*\/?>/gi, '\n');

        // Remove remaining HTML tags
        md = md.replace(/<[^>]+>/g, '');

        // Decode HTML entities
        md = md.replace(/&nbsp;/g, ' ');
        md = md.replace(/&amp;/g, '&');
        md = md.replace(/&lt;/g, '<');
        md = md.replace(/&gt;/g, '>');
        md = md.replace(/&quot;/g, '"');

        // Clean up extra whitespace
        md = md.replace(/\n{3,}/g, '\n\n');
        md = md.trim();

        return md;
    }

    // Handle tab switching
    function handleTabChange(tab) {
        if (tab === activeTab) return;

        if (tab === 'wysiwyg' && editor) {
            // Switching to WYSIWYG - convert markdown to HTML
            if (value && DOMPurify) {
                try {
                    const rawHtml = marked.parse(value);
                    const safeHtml = DOMPurify.sanitize(rawHtml);
                    editor.commands.setContent(safeHtml);
                } catch (e) {
                    console.error('Error converting markdown to HTML:', e);
                }
            }
        }

        activeTab = tab;
    }

    // File upload functions
    async function uploadFile(file, fileType = 'image') {
        uploading = true;
        uploadError = '';

        try {
            const base64 = await fileToBase64(file);

            // Create FormData for form action submission
            const formData = new FormData();
            formData.append('file_name', file.name);
            formData.append('file_content', base64);
            formData.append('file_type', fileType);

            const response = await fetch('?/upload_editor_file', {
                method: 'POST',
                body: formData,
            });

            // Use SvelteKit's deserialize to properly parse the action response
            const result = deserialize(await response.text());

            // Handle successful response
            if (result.type === 'success' && result.data) {
                if (result.data.url) {
                    return result.data.url;
                }
            }

            // Handle error cases
            if (result.type === 'error' || result.type === 'failure') {
                throw new Error(result.data?.message || m.markdownEditor_uploadFailed());
            }

            throw new Error(m.markdownEditor_uploadFailed());
        } catch (error) {
            uploadError = error.message;
            throw error;
        } finally {
            uploading = false;
        }
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    }

    async function handleImageUpload(file, mode = 'inline') {
        if (!file || !editor) return;

        try {
            if (mode === 'inline') {
                // Upload and insert as inline image
                const url = await uploadFile(file, 'image');
                editor.chain().focus().setImage({ src: url, alt: file.name }).run();
            } else {
                // Upload as attachment and insert as link
                const url = await uploadFile(file, 'attachment');
                editor.chain().focus().insertContent(`[${file.name}](${url})`).run();
            }
        } catch (error) {
            console.error('Image upload failed:', error);
        }

        imageDropdownOpen = false;
    }

    function triggerImageInput(mode) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => {
            const file = e.target.files?.[0];
            if (file) {
                handleImageUpload(file, mode);
            }
        };
        input.click();
        imageDropdownOpen = false;
    }

    function triggerAttachmentInput() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.zip';
        input.onchange = async (e) => {
            const file = e.target.files?.[0];
            if (file) {
                try {
                    const url = await uploadFile(file, 'attachment');
                    if (editor) {
                        editor.chain().focus().insertContent(`[${file.name}](${url})`).run();
                    }
                } catch (error) {
                    console.error('Attachment upload failed:', error);
                }
            }
        };
        input.click();
    }

    function insertLink() {
        if (!editor) return;

        const previousUrl = editor.getAttributes('link').href;
        const url = window.prompt(m.markdownEditor_enterUrl(), previousUrl);

        if (url === null) return;

        if (url === '') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run();
            return;
        }

        editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    }

    // Derived active states for toolbar buttons (reactive)
    let isBoldActive = $derived(editorState >= 0 && editor?.isActive('bold'));
    let isItalicActive = $derived(editorState >= 0 && editor?.isActive('italic'));
    let isUnderlineActive = $derived(editorState >= 0 && editor?.isActive('underline'));
    let isStrikeActive = $derived(editorState >= 0 && editor?.isActive('strike'));
    let isH1Active = $derived(editorState >= 0 && editor?.isActive('heading', { level: 1 }));
    let isH2Active = $derived(editorState >= 0 && editor?.isActive('heading', { level: 2 }));
    let isH3Active = $derived(editorState >= 0 && editor?.isActive('heading', { level: 3 }));
    let isBulletListActive = $derived(editorState >= 0 && editor?.isActive('bulletList'));
    let isOrderedListActive = $derived(editorState >= 0 && editor?.isActive('orderedList'));
    // TipTap reports whether the commands can run in the current selection; a
    // first-level item cannot be outdented and a first child cannot be indented.
    let canIndentListItem = $derived(
        editorState >= 0 && !!editor?.can().sinkListItem('listItem')
    );
    let canOutdentListItem = $derived(
        editorState >= 0 && !!editor?.can().liftListItem('listItem')
    );
    let isBlockquoteActive = $derived(editorState >= 0 && editor?.isActive('blockquote'));
    let isLinkActive = $derived(editorState >= 0 && editor?.isActive('link'));
</script>

{#if label}
    <Label for={id} class="block mb-2">{label}{#if required} <span class="text-red-500">*</span>{/if}</Label>
{/if}

<div class="border border-gray-300 rounded-lg overflow-hidden">
    <!-- Tab Switcher -->
    <div class="flex border-b border-gray-200 bg-gray-50">
        <button
            type="button"
            class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'wysiwyg' ? 'bg-white border-b-2 border-blue-500 text-blue-600' : 'text-gray-600 hover:text-gray-900'}"
            onclick={() => handleTabChange('wysiwyg')}
        >
            {m.markdownEditor_liveEdit()}
        </button>
        <button
            type="button"
            class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'markdown' ? 'bg-white border-b-2 border-blue-500 text-blue-600' : 'text-gray-600 hover:text-gray-900'}"
            onclick={() => handleTabChange('markdown')}
        >
            {m.markdownEditor_markdown()}
        </button>
    </div>

    <!-- WYSIWYG Mode -->
    <div class={activeTab === 'wysiwyg' ? '' : 'hidden'}>
        <!-- WYSIWYG Toolbar -->
        <div class="flex flex-wrap items-center gap-1 p-2 border-b border-gray-200 bg-gray-50">
            <!-- Text Formatting -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isBoldActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleBold().run()}
                title={m.markdownEditor_bold()}
            >
                <Bold class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isItalicActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleItalic().run()}
                title={m.markdownEditor_italic()}
            >
                <Italic class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isUnderlineActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleUnderline().run()}
                title={m.markdownEditor_underline()}
            >
                <UnderlineIcon class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isStrikeActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleStrike().run()}
                title={m.markdownEditor_strikethrough()}
            >
                <Strikethrough class="w-4 h-4" />
            </button>

            <div class="w-px h-6 bg-gray-300 mx-1"></div>

            <!-- Headings -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 text-sm {isH1Active ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
                title={m.markdownEditor_heading1()}
            >
                <Heading1 class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 text-sm {isH2Active ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
                title={m.markdownEditor_heading2()}
            >
                <Heading2 class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 text-sm {isH3Active ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
                title={m.markdownEditor_heading3()}
            >
                <Heading3 class="w-4 h-4" />
            </button>

            <div class="w-px h-6 bg-gray-300 mx-1"></div>

            <!-- Lists -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isBulletListActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleBulletList().run()}
                title={m.markdownEditor_bulletList()}
            >
                <List class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isOrderedListActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleOrderedList().run()}
                title={m.markdownEditor_orderedList()}
            >
                <ListOrdered class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isBlockquoteActive ? 'bg-gray-200' : ''}"
                onclick={() => editor?.chain().focus().toggleBlockquote().run()}
                title={m.markdownEditor_quote()}
            >
                <Quote class="w-4 h-4" />
            </button>

            <!-- List level: only meaningful inside a list, so disabled elsewhere -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-40"
                onclick={() => editor?.chain().focus().sinkListItem('listItem').run()}
                disabled={!canIndentListItem}
                title={m.markdownEditor_indentList()}
            >
                <IndentIncrease class="w-4 h-4" />
            </button>
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 disabled:opacity-40"
                onclick={() => editor?.chain().focus().liftListItem('listItem').run()}
                disabled={!canOutdentListItem}
                title={m.markdownEditor_outdentList()}
            >
                <IndentDecrease class="w-4 h-4" />
            </button>

            <div class="w-px h-6 bg-gray-300 mx-1"></div>

            <!-- Table Dropdown -->
            <div class="relative">
                <button
                    type="button"
                    class="p-1.5 rounded hover:bg-gray-200 flex items-center gap-0.5"
                    onclick={() => tableDropdownOpen = !tableDropdownOpen}
                    title={m.markdownEditor_table()}
                >
                    <Columns3 class="w-4 h-4" />
                    <ChevronDown class="w-3 h-3" />
                </button>
                {#if tableDropdownOpen}
                    <div class="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-[180px]">
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100"
                            onclick={() => { editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); tableDropdownOpen = false; }}
                        >
                            {m.markdownEditor_insertTable()}
                        </button>
                        <div class="border-t border-gray-200"></div>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().addColumnBefore().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().addColumnBefore()}
                        >
                            {m.markdownEditor_addColumnBefore()}
                        </button>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().addColumnAfter().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().addColumnAfter()}
                        >
                            {m.markdownEditor_addColumnAfter()}
                        </button>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().deleteColumn().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().deleteColumn()}
                        >
                            {m.markdownEditor_deleteColumn()}
                        </button>
                        <div class="border-t border-gray-200"></div>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().addRowBefore().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().addRowBefore()}
                        >
                            {m.markdownEditor_addRowBefore()}
                        </button>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().addRowAfter().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().addRowAfter()}
                        >
                            {m.markdownEditor_addRowAfter()}
                        </button>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().deleteRow().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().deleteRow()}
                        >
                            {m.markdownEditor_deleteRow()}
                        </button>
                        <div class="border-t border-gray-200"></div>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 text-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
                            onclick={() => { editor?.chain().focus().deleteTable().run(); tableDropdownOpen = false; }}
                            disabled={!editor?.can().deleteTable()}
                        >
                            {m.markdownEditor_deleteTable()}
                        </button>
                    </div>
                {/if}
            </div>

            <!-- Link -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200 {isLinkActive ? 'bg-gray-200' : ''}"
                onclick={insertLink}
                title={m.markdownEditor_link()}
            >
                <LinkIcon class="w-4 h-4" />
            </button>

            <!-- Image Dropdown -->
            <div class="relative">
                <button
                    type="button"
                    class="p-1.5 rounded hover:bg-gray-200 flex items-center gap-0.5"
                    onclick={() => imageDropdownOpen = !imageDropdownOpen}
                    title={m.markdownEditor_image()}
                >
                    <ImageIcon class="w-4 h-4" />
                    <ChevronDown class="w-3 h-3" />
                </button>
                {#if imageDropdownOpen}
                    <div class="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-[160px]">
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                            onclick={() => triggerImageInput('inline')}
                        >
                            <ImageIcon class="w-4 h-4" />
                            {m.markdownEditor_insertInline()}
                        </button>
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                            onclick={() => triggerImageInput('attachment')}
                        >
                            <Paperclip class="w-4 h-4" />
                            {m.markdownEditor_insertAsLink()}
                        </button>
                    </div>
                {/if}
            </div>

            <!-- Attachment -->
            <button
                type="button"
                class="p-1.5 rounded hover:bg-gray-200"
                onclick={triggerAttachmentInput}
                title={m.markdownEditor_attachment()}
                disabled={uploading}
            >
                {#if uploading}
                    <Spinner size="4" />
                {:else}
                    <Paperclip class="w-4 h-4" />
                {/if}
            </button>
        </div>

        <!-- Editor Area -->
        <div
            bind:this={editorElement}
            class="bg-white min-h-[200px]"
            style="min-height: {rows * 24}px"
            ondragover={(e) => e.preventDefault()}
            role="textbox"
            aria-multiline="true"
            tabindex="0"
        ></div>

        {#if uploadError}
            <div class="px-4 py-2 text-sm text-red-600 bg-red-50 border-t border-red-200">
                {uploadError}
            </div>
        {/if}

        <div class="px-4 py-2 text-xs text-gray-500 bg-gray-50 border-t border-gray-200">
            {m.markdownEditor_dragDropHint()}
        </div>
    </div>

    <!-- Markdown Mode -->
    <div class={activeTab === 'markdown' ? '' : 'hidden'}>
        <Textarea
            {id}
            {name}
            bind:value={value}
            placeholder={placeholder || m.markdownEditor_placeholder()}
            {rows}
            class="font-mono w-full border-0 rounded-none focus:ring-0"
        />
        <div class="px-4 py-2 text-xs text-gray-500 bg-gray-50 border-t border-gray-200">
            {m.markdownEditor_supportsMarkdown()}
        </div>
    </div>
</div>

<!-- Hidden input for form submission -->
<input type="hidden" {name} bind:value={value} />

<style>
    :global(.ProseMirror) {
        outline: none;
    }

    :global(.ProseMirror p.is-editor-empty:first-child::before) {
        content: attr(data-placeholder);
        float: left;
        color: #9ca3af;
        pointer-events: none;
        height: 0;
    }

    :global(.ProseMirror img) {
        max-width: 100%;
        height: auto;
        border-radius: 0.375rem;
    }

    :global(.ProseMirror img.ProseMirror-selectednode) {
        outline: 2px solid #3b82f6;
    }

    /* Table styles */
    :global(.ProseMirror table) {
        border-collapse: collapse;
        table-layout: fixed;
        width: 100%;
        margin: 1rem 0;
        overflow: hidden;
    }

    :global(.ProseMirror td),
    :global(.ProseMirror th) {
        min-width: 1em;
        border: 1px solid #d1d5db;
        padding: 0.5rem;
        vertical-align: top;
        box-sizing: border-box;
        position: relative;
    }

    :global(.ProseMirror th) {
        font-weight: 600;
        text-align: left;
        background-color: #f3f4f6;
    }

    :global(.ProseMirror .selectedCell:after) {
        z-index: 2;
        position: absolute;
        content: "";
        left: 0;
        right: 0;
        top: 0;
        bottom: 0;
        background: rgba(59, 130, 246, 0.15);
        pointer-events: none;
    }

    :global(.ProseMirror .column-resize-handle) {
        position: absolute;
        right: -2px;
        top: 0;
        bottom: -2px;
        width: 4px;
        background-color: #3b82f6;
        pointer-events: none;
    }

    :global(.ProseMirror.resize-cursor) {
        cursor: col-resize;
    }
</style>
