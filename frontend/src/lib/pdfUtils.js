import { jsPDF } from 'jspdf';
import { formatDateRange, getDisplayOrganizers, getDisplayVenue } from '$lib/utils.js';

// Font state (shared across calls)
let fontLoaded = false;
let fontBase64Regular = '';
let fontBase64Bold = '';

/**
 * Load Korean fonts for PDF generation
 * Loads both regular and bold variants of NotoSansKR
 * @returns {Promise<boolean>} - True if fonts loaded successfully
 */
export async function loadKoreanFonts() {
    if (fontLoaded) return true;

    try {
        const loadFont = async (url) => {
            const response = await fetch(url);
            const blob = await response.blob();
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            });
        };

        const [regular, bold] = await Promise.all([
            loadFont('/fonts/NotoSansKR-Regular.ttf'),
            loadFont('/fonts/NotoSansKR-Bold.ttf')
        ]);

        fontBase64Regular = regular;
        fontBase64Bold = bold;
        fontLoaded = true;
        return true;
    } catch (error) {
        console.error('Failed to load Korean fonts:', error);
        return false;
    }
}

/**
 * Check if Korean fonts are loaded
 * @returns {boolean}
 */
export function areFontsLoaded() {
    return fontLoaded;
}

/**
 * Add Korean fonts to a jsPDF document
 * @param {jsPDF} doc - The jsPDF document instance
 */
function addFontsToDoc(doc) {
    if (fontLoaded && fontBase64Regular && fontBase64Bold) {
        doc.addFileToVFS('NotoSansKR-Regular.ttf', fontBase64Regular);
        doc.addFileToVFS('NotoSansKR-Bold.ttf', fontBase64Bold);
        doc.addFont('NotoSansKR-Regular.ttf', 'NotoSansKR', 'normal');
        doc.addFont('NotoSansKR-Bold.ttf', 'NotoSansKR', 'bold');
    }
}

/**
 * Get the appropriate font family based on font loading status
 * @returns {string} - Font family name
 */
function getFontFamily() {
    return fontLoaded ? 'NotoSansKR' : 'helvetica';
}

/**
 * Create an addLine helper function for a jsPDF document
 * @param {jsPDF} doc - The jsPDF document instance
 * @param {Object} options - Options for the helper
 * @param {number} options.centerX - X position for centered text
 * @param {number} options.maxWidth - Maximum width for text wrapping
 * @returns {Object} - Object with addLine function and currY getter/setter
 */
function createAddLineHelper(doc, { centerX, maxWidth }) {
    const fontFamily = getFontFamily();
    let currY = 0;

    const addLine = (text, { fontWeight = 'normal', fontSize = 15, fixedY = null } = {}) => {
        doc.setFont(fontFamily, fontWeight);
        doc.setFontSize(fontSize);
        const splitText = doc.splitTextToSize(text || '', maxWidth);

        if (fixedY !== null) {
            splitText.forEach((line) => {
                doc.text(line, centerX, fixedY, { align: 'center' });
            });
        } else {
            splitText.forEach((line, index) => {
                doc.text(line, centerX, currY + (index * 10), { align: 'center' });
            });
            currY += splitText.length * 10;
        }
    };

    return {
        addLine,
        get currY() { return currY; },
        set currY(val) { currY = val; }
    };
}

/**
 * Generate a nametag PDF
 * Handles long names/institutes with multi-line wrapping and vertical centering
 * In landscape mode, content is rotated 90 degrees clockwise
 * @param {Object} options
 * @param {string} options.name - Attendee name
 * @param {string} options.institute - Attendee institution
 * @param {string} options.role - Role to display (e.g., 'Participant', 'Speaker')
 * @param {number} [options.id] - Optional attendee ID to display
 * @param {number} [options.paperWidth=90] - Paper width in mm
 * @param {number} [options.paperHeight=100] - Paper height in mm
 * @param {string} [options.orientation='portrait'] - Paper orientation ('portrait' or 'landscape')
 * @returns {Promise<string>} - Blob URI of the generated PDF
 */
/**
 * Render a single nametag page onto an existing jsPDF document
 * @param {jsPDF} doc - The jsPDF document instance
 * @param {Object} options - Nametag options
 */
function renderNametagPage(doc, { name, institute, role, id, paperWidth, paperHeight, orientation }) {
    const fontFamily = getFontFamily();
    const contentWidth = paperWidth;
    const contentHeight = paperHeight;

    const scaleX = contentWidth / 90;
    const scaleY = contentHeight / 100;
    const scale = Math.min(scaleX, scaleY) * ((Math.sin((contentWidth - contentHeight) / Math.max(contentWidth, contentHeight) * (Math.PI/4)) + 1));

    const centerX = contentWidth / 2;
    const maxWidth = contentWidth - 10 * scaleX;

    const drawCenteredText = (text, logicalX, logicalY) => {
        if (orientation === 'landscape') {
            const textWidth = doc.getTextWidth(text);
            const paperX = logicalY;
            const paperY = logicalX + textWidth / 2;
            doc.text(text, paperX, paperY, { angle: 90 });
        } else {
            doc.text(text, logicalX, logicalY, { align: 'center' });
        }
    };

    if (id !== undefined) {
        doc.setFont(fontFamily, 'bold');
        doc.setFontSize(10 * scale);
        drawCenteredText(`${id}`, centerX, 10 * scaleY);
    }

    const nameFontSize = Math.round(30 * scale);
    const instituteFontSize = Math.round(20 * scale);
    const roleFontSize = Math.round(23 * scale);

    doc.setFont(fontFamily, 'bold');
    doc.setFontSize(nameFontSize);
    const nameLines = doc.splitTextToSize(name || '', maxWidth);
    const nameLineHeight = 12 * scale;

    doc.setFont(fontFamily, 'normal');
    doc.setFontSize(instituteFontSize);
    const instituteLines = doc.splitTextToSize(institute || '', maxWidth);
    const instituteLineHeight = 7 * scale;

    const nameHeight = nameLines.length * nameLineHeight;
    const instituteHeight = instituteLines.length * instituteLineHeight;
    const gap = 5 * scale;
    const totalHeight = nameHeight + gap + instituteHeight;

    const topBound = 18 * scaleY;
    const bottomBound = contentHeight - 22 * scaleY;
    const availableHeight = bottomBound - topBound;
    const startY = topBound + (availableHeight - totalHeight) / 2;

    doc.setFont(fontFamily, 'bold');
    doc.setFontSize(nameFontSize);
    let currentY = startY + nameLineHeight * 0.7;
    nameLines.forEach((line, index) => {
        drawCenteredText(line, centerX, currentY + index * nameLineHeight);
    });

    doc.setFont(fontFamily, 'normal');
    doc.setFontSize(instituteFontSize);
    currentY = startY + nameHeight + gap + instituteLineHeight * 0.7;
    instituteLines.forEach((line, index) => {
        drawCenteredText(line, centerX, currentY + index * instituteLineHeight);
    });

    const dividerY = contentHeight - 18 * scaleY;
    doc.setLineWidth(1 * scale);
    if (orientation === 'landscape') {
        const dividerX = dividerY;
        doc.line(dividerX, 5 * scaleX, dividerX, contentWidth - 5 * scaleX);
    } else {
        doc.line(5 * scaleX, dividerY, contentWidth - 5 * scaleX, dividerY);
    }

    doc.setFont(fontFamily, 'bold');
    doc.setFontSize(roleFontSize);
    drawCenteredText(role || 'Participant', centerX, contentHeight - 7 * scaleY);
}

/**
 * Compute jsPDF orientation from user orientation and paper dimensions
 */
function computePdfOrientation(orientation, paperWidth, paperHeight) {
    let pdf_orientation = orientation;
    if (orientation === 'portrait' && paperWidth > paperHeight) {
        pdf_orientation = 'landscape';
    } else if (orientation === 'landscape' && paperWidth > paperHeight) {
        pdf_orientation = 'portrait';
    }
    return pdf_orientation;
}

export async function generateNametagPDF({ name, institute, role, id, paperWidth = 90, paperHeight = 100, orientation = 'portrait' }) {
    await loadKoreanFonts();

    const doc = new jsPDF({
        orientation: computePdfOrientation(orientation, paperWidth, paperHeight),
        unit: 'mm',
        format: [paperWidth, paperHeight]
    });

    addFontsToDoc(doc);
    renderNametagPage(doc, { name, institute, role, id, paperWidth, paperHeight, orientation });

    return doc.output('bloburi');
}

/**
 * Generate a batch nametag PDF with one nametag per page
 * @param {Object} options
 * @param {Array<{name: string, institute: string, id?: number}>} options.attendees - List of attendees
 * @param {string} options.role - Role to display on all nametags
 * @param {number} [options.paperWidth=90] - Paper width in mm
 * @param {number} [options.paperHeight=100] - Paper height in mm
 * @param {string} [options.orientation='portrait'] - Paper orientation
 * @returns {Promise<string>} - Blob URI of the generated PDF
 */
export async function generateBatchNametagPDF({ attendees, role, paperWidth = 90, paperHeight = 100, orientation = 'portrait' }) {
    await loadKoreanFonts();

    const doc = new jsPDF({
        orientation: computePdfOrientation(orientation, paperWidth, paperHeight),
        unit: 'mm',
        format: [paperWidth, paperHeight]
    });

    addFontsToDoc(doc);

    attendees.forEach((attendee, index) => {
        if (index > 0) {
            doc.addPage([paperWidth, paperHeight], computePdfOrientation(orientation, paperWidth, paperHeight));
        }
        renderNametagPage(doc, {
            name: attendee.name,
            institute: attendee.institute,
            role,
            id: attendee.id,
            paperWidth,
            paperHeight,
            orientation
        });
    });

    return doc.output('bloburi');
}

/**
 * Generate a certificate PDF
 * Vertically centered content with table format
 * @param {Object} options
 * @param {Object} options.attendee - Attendee object with name, institute
 * @param {Object} options.event - Event object with name, start_date, end_date, venue, organizers_en, organizers_ko
 * @param {Object} options.messages - i18n message functions
 * @param {string} [options.outputFormat='bloburi'] - Output format: 'bloburi' or 'datauristring'
 * @returns {Promise<string>} - Blob URI or data URI string of the generated PDF
 */
export async function generateCertificatePDF({ attendee, event, messages, outputFormat = 'bloburi' }) {
    await loadKoreanFonts();

    const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: [210, 297]
    });

    addFontsToDoc(doc);
    const fontFamily = getFontFamily();
    const centerX = 105;
    const pageHeight = 297;

    // Header: Issue date and title (fixed position)
    doc.setFont(fontFamily, 'normal');
    doc.setFontSize(10);
    doc.text(`${messages.certIssueDate()}: ${new Date().toLocaleDateString()}`, centerX, 15, { align: 'center' });

    doc.setFont(fontFamily, 'bold');
    doc.setFontSize(30);
    doc.text(messages.certTitle(), centerX, 45, { align: 'center' });

    // Footer at bottom
    doc.setFont(fontFamily, 'normal');
    doc.setFontSize(10);
    doc.text(messages.certFooter(), centerX, 287, { align: 'center' });

    // Define table rows (label, value pairs)
    const organizers = getDisplayOrganizers(event);
    const tableData = [
        { label: messages.certName(), value: attendee.name },
        { label: '', value: '' }, // spacer
        { label: messages.certInstitute(), value: attendee.institute },
        { label: '', value: '' }, // spacer
        { label: messages.certHasAttended(), value: event.name },
        { label: '', value: '' }, // spacer
        { label: messages.certOn(), value: formatDateRange(event.start_date, event.end_date) },
        { label: '', value: '' }, // spacer
        { label: messages.certHeldAt(), value: getDisplayVenue(event) },
        { label: '', value: '' }, // spacer
        { label: '', value: '' }, // spacer
        { label: '', value: '' }, // spacer
        { label: messages.certAsParticipant(), value: '' },
        { label: '', value: '' }, // spacer
        { label: '', value: organizers }
    ];

    // Calculate dimensions
    const fontSize = 12;
    const lineHeight = 6; // mm per line
    const spacerHeight = 3; // height for spacer rows
    const labelWidth = 50;
    const tableX = 30; // left margin for table
    const valueMaxWidth = 100; // max width for value text
    const centeredMaxWidth = 150; // max width for centered text

    // Set font size for text measurement
    doc.setFontSize(fontSize);

    // Pre-calculate line counts for each row
    const rowData = tableData.map(row => {
        if (row.label === '' && row.value === '') {
            // Spacer
            return { ...row, lines: [], height: spacerHeight, type: 'spacer' };
        } else if (row.value === '') {
            // Label only (centered) - wrap if needed
            doc.setFont(fontFamily, 'bold');
            const lines = doc.splitTextToSize(row.label || '', centeredMaxWidth);
            return { ...row, lines, height: lines.length * lineHeight, type: 'centered-label' };
        } else if (row.label === '') {
            // Value only (centered) - wrap if needed
            doc.setFont(fontFamily, 'bold');
            const lines = doc.splitTextToSize(row.value || '', centeredMaxWidth);
            return { ...row, lines, height: lines.length * lineHeight, type: 'centered-value' };
        } else {
            // Label: Value pair - wrap value if needed
            doc.setFont(fontFamily, 'normal');
            const lines = doc.splitTextToSize(row.value || '', valueMaxWidth);
            return { ...row, lines, height: lines.length * lineHeight, type: 'label-value' };
        }
    });

    // Calculate total content height
    let contentHeight = 0;
    rowData.forEach(row => {
        contentHeight += row.height;
    });

    // Available space (between header and footer)
    const topBound = 55; // below title
    const bottomBound = 275;
    const availableHeight = bottomBound - topBound;

    // Calculate starting Y to vertically center the table content
    const startY = topBound + (availableHeight - contentHeight) / 2;

    // Draw table rows
    let currentY = startY;
    doc.setFontSize(fontSize);

    rowData.forEach(row => {
        if (row.type === 'spacer') {
            currentY += row.height;
        } else if (row.type === 'centered-label') {
            doc.setFont(fontFamily, 'bold');
            row.lines.forEach((line, idx) => {
                doc.text(line, centerX, currentY + idx * lineHeight, { align: 'center' });
            });
            currentY += row.height;
        } else if (row.type === 'centered-value') {
            doc.setFont(fontFamily, 'bold');
            row.lines.forEach((line, idx) => {
                doc.text(line, centerX, currentY + idx * lineHeight, { align: 'center' });
            });
            currentY += row.height;
        } else if (row.type === 'label-value') {
            // Draw label (bold, right-aligned)
            doc.setFont(fontFamily, 'bold');
            doc.text(row.label, tableX + labelWidth, currentY, { align: 'right' });
            // Draw value lines (normal)
            doc.setFont(fontFamily, 'normal');
            row.lines.forEach((line, idx) => {
                doc.text(line, tableX + labelWidth + 5, currentY + idx * lineHeight);
            });
            currentY += row.height;
        }
    });

    return doc.output(outputFormat);
}
