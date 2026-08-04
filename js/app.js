/**
 * Core Application Controller
 * Connects file uploads, filter inputs, calculation engines, UI renderers, and exports.
 */

(function () {
    let originalData = null;

    document.addEventListener("DOMContentLoaded", function () {
        // Initialize UI navigation and listeners
        UiManager.init(handleFilterChange);

        // Bind File Drag and Drop events
        const uploadCard = document.getElementById('upload-card');
        const fileInput = document.getElementById('file-input');

        uploadCard.addEventListener('click', () => fileInput.click());
        
        uploadCard.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadCard.classList.add('dragover');
        });

        uploadCard.addEventListener('dragleave', () => {
            uploadCard.classList.remove('dragover');
        });

        uploadCard.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadCard.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                processFile(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                processFile(e.target.files[0]);
            }
        });

        // "Download Template" button handler
        document.getElementById('btn-download-template').addEventListener('click', () => {
            DataParser.downloadTemplate();
        });

        // Wire Export download triggers
        document.getElementById('btn-export-exec-pdf').addEventListener('click', () => {
            if (!originalData) return;
            const currentKpis = getActiveKpis();
            ExportManager.exportExecutivePdf(currentKpis);
        });

        document.getElementById('btn-export-exec-xlsx').addEventListener('click', () => {
            if (!originalData) return;
            const currentKpis = getActiveKpis();
            const filtered = getActiveFilteredData();
            ExportManager.exportExecutiveExcel(filtered, currentKpis);
        });

        document.getElementById('btn-export-batch-pdf').addEventListener('click', () => {
            if (!originalData) return;
            const currentKpis = getActiveKpis();
            const batchName = document.getElementById('filter-batch').value;
            ExportManager.exportBatchPdf(currentKpis, batchName);
        });

        document.getElementById('btn-export-batch-xlsx').addEventListener('click', () => {
            if (!originalData) return;
            const batchName = document.getElementById('filter-batch').value;
            ExportManager.exportBatchExcel(originalData, batchName);
        });
    });

    /**
     * Process incoming uploaded spreadsheet
     */
    function processFile(file) {
        DataParser.parseFile(
            file,
            (parsedData) => {
                originalData = parsedData;
                initDashboardFlow();
            }
        );
    }

    /**
     * Initialize filters and trigger first render
     */
    function initDashboardFlow() {
        UiManager.populateFilters(originalData);
        handleFilterChange();
    }

    /**
     * Get active filters state from UI
     */
    function getActiveFilters() {
        return {
            category: document.getElementById('filter-category').value,
            batch: document.getElementById('filter-batch').value,
            teacher: document.getElementById('filter-teacher').value,
            state: document.getElementById('filter-state').value
        };
    }

    /**
     * Return filtered datasets matching current controls
     */
    function getActiveFilteredData() {
        const filters = getActiveFilters();
        return KpiEngine.filterData(originalData, filters);
    }

    /**
     * Calculate and return current KPIs
     */
    function getActiveKpis() {
        const filtered = getActiveFilteredData();
        return KpiEngine.calculateKPIs(filtered);
    }

    /**
     * Recalculate KPIs and redraw charts when user adjusts filter selects
     */
    function handleFilterChange() {
        if (!originalData) return;

        // Repopulate filter dropdown values sequentially to support cascade hierarchy
        UiManager.populateFilters(originalData, getActiveFilters());

        const filtered = getActiveFilteredData();
        const kpis = KpiEngine.calculateKPIs(filtered);

        UiManager.renderDashboard(kpis, filtered, originalData);
    }

})();
