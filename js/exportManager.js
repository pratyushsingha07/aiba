/**
 * Export Manager Module
 * Handles Excel exports using SheetJS and PDF exports using jsPDF and html2canvas.
 */

window.ExportManager = (function () {

    /**
     * Export Executive Excel Workbook (Complete Dashboard Data)
     */
    function exportExecutiveExcel(data, kpis) {
        if (!data) return;

        const wb = XLSX.utils.book_new();

        // 1. KPI summary sheet
        const kpiRows = [
            { Metric: "Total Gross Sales", Value: kpis.grossRevenue },
            { Metric: "Total Net Revenue", Value: kpis.netRevenue },
            { Metric: "Refund Amount", Value: kpis.refundAmount },
            { Metric: "Refund %", Value: kpis.refundPercent / 100 },
            { Metric: "Total Orders", Value: kpis.orders },
            { Metric: "Average Selling Price (ASP)", Value: kpis.averageSellingPrice },
            { Metric: "Daily Run Rate (DRR)", Value: kpis.dailyRunRate },
            { Metric: "Target Achievement %", Value: kpis.targetAchievedPercent / 100 },
            { Metric: "Batch Profit", Value: kpis.profit }
        ];
        const wsSummary = XLSX.utils.json_to_sheet(kpiRows);
        XLSX.utils.book_append_sheet(wb, wsSummary, "Summary KPIs");

        // 2. Sales Trend sheet
        const salesTrend = [];
        const uniqueDates = [...new Set(data.sales.map(s => s.Date))].sort();
        uniqueDates.forEach(date => {
            const dateSales = data.sales.filter(s => s.Date === date);
            const amt = dateSales.reduce((acc, s) => acc + s.Sales, 0);
            salesTrend.push({ Date: date, Sales: amt, Orders: dateSales.length });
        });
        const wsTrend = XLSX.utils.json_to_sheet(salesTrend);
        XLSX.utils.book_append_sheet(wb, wsTrend, "Daily Sales");

        // 3. Batch Performance
        const batchPerf = KpiEngine.getBatchPerformance(data);
        const wsBatch = XLSX.utils.json_to_sheet(batchPerf);
        XLSX.utils.book_append_sheet(wb, wsBatch, "Batch Performance");

        // 4. Category Performance
        const catPerf = KpiEngine.getCategoryPerformance(data);
        const wsCat = XLSX.utils.json_to_sheet(catPerf);
        XLSX.utils.book_append_sheet(wb, wsCat, "Category Performance");

        // Write file
        XLSX.writeFile(wb, "BI_Executive_Summary_Report.xlsx");
    }

    /**
     * Export Selected Batch Excel Workbook
     */
    function exportBatchExcel(data, batchName) {
        if (!data || !batchName || batchName === 'All') {
            alert("Please select a specific Batch from filters to export Batch Report.");
            return;
        }

        const wb = XLSX.utils.book_new();

        // Filter sales for the selected batch
        const batchSales = data.sales.filter(s => s.Batch === batchName);
        const batchRefunds = data.refunds.filter(r => r.Batch === batchName);

        const wsSales = XLSX.utils.json_to_sheet(batchSales);
        XLSX.utils.book_append_sheet(wb, wsSales, "Sales Transactions");

        const wsRefunds = XLSX.utils.json_to_sheet(batchRefunds);
        XLSX.utils.book_append_sheet(wb, wsRefunds, "Refund Transactions");

        XLSX.writeFile(wb, `BI_Batch_Report_${batchName.replace(/\s+/g, '_')}.xlsx`);
    }

    /**
     * Export Executive Summary PDF using jsPDF + html2canvas
     */
    function exportExecutivePdf(kpis) {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        
        // Target active tab element
        const element = document.querySelector('main');

        // Temporarily adjust UI to light mode for cleaner print, then restore
        const currentTheme = document.documentElement.getAttribute('data-theme');
        document.documentElement.setAttribute('data-theme', 'light');

        // Let UI resize and update colors before capturing
        setTimeout(() => {
            html2canvas(element, {
                scale: 2,
                useCORS: true,
                backgroundColor: "#ffffff"
            }).then(canvas => {
                const imgData = canvas.toDataURL('image/jpeg', 0.95);
                const imgWidth = pdfWidth - 20; // 10mm margins
                const imgHeight = (canvas.height * imgWidth) / canvas.width;
                
                pdf.setFont("helvetica", "bold");
                pdf.setFontSize(18);
                pdf.setTextColor(15, 23, 42); // Navy Slate color
                pdf.text("AI Business Intelligence Dashboard - Executive Report", 10, 15);
                pdf.setFontSize(10);
                pdf.setFont("helvetica", "normal");
                pdf.setTextColor(100, 116, 139);
                pdf.text(`Generated on: ${new Date().toLocaleDateString()} | Net Revenue: ${formatCurrency(kpis.netRevenue)}`, 10, 22);

                pdf.addImage(imgData, 'JPEG', 10, 26, imgWidth, imgHeight);
                pdf.save("Executive_Dashboard_Report.pdf");

                // Restore theme
                document.documentElement.setAttribute('data-theme', currentTheme);
            });
        }, 300);
    }

    /**
     * Export Selected Batch PDF using jsPDF + html2canvas
     */
    function exportBatchPdf(kpis, batchName) {
        if (!batchName || batchName === 'All') {
            alert("Please select a specific Batch from filters to export Batch Report.");
            return;
        }

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();

        // Target the active tab element (or specific dashboard-card)
        const element = document.getElementById('batch-dashboard');

        const currentTheme = document.documentElement.getAttribute('data-theme');
        document.documentElement.setAttribute('data-theme', 'light');

        setTimeout(() => {
            html2canvas(element, {
                scale: 2,
                useCORS: true,
                backgroundColor: "#ffffff"
            }).then(canvas => {
                const imgData = canvas.toDataURL('image/jpeg', 0.95);
                const imgWidth = pdfWidth - 20;
                const imgHeight = (canvas.height * imgWidth) / canvas.width;

                pdf.setFont("helvetica", "bold");
                pdf.setFontSize(18);
                pdf.text(`BI Batch Report - ${batchName}`, 10, 15);
                pdf.setFontSize(10);
                pdf.setFont("helvetica", "normal");
                pdf.text(`Generated on: ${new Date().toLocaleDateString()} | Net Profit margin: 45%`, 10, 22);

                pdf.addImage(imgData, 'JPEG', 10, 26, imgWidth, imgHeight);
                pdf.save(`Batch_Report_${batchName.replace(/\s+/g, '_')}.pdf`);

                document.documentElement.setAttribute('data-theme', currentTheme);
            });
        }, 300);
    }

    function formatCurrency(val) {
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
    }

    return {
        exportExecutiveExcel,
        exportBatchExcel,
        exportExecutivePdf,
        exportBatchPdf
    };
})();
