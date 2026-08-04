/**
 * Data Parser Module for BI Dashboard
 * Handles SheetJS parsing, Auto column mapping, and Demo data generation.
 */

window.DataParser = (function () {
    // Standard system column definitions
    const EXPECTED_COLUMNS = {
        sales: ['Date', 'OrderID', 'Category', 'Batch', 'Teacher', 'State', 'Sales', 'Admissions'],
        refunds: ['Date', 'OrderID', 'RefundAmount', 'Category', 'Batch', 'Teacher', 'State'],
        targets: ['Month', 'Category', 'Target'],
        batches: ['Batch', 'Capacity', 'Teacher', 'Profit']
    };

    // Alternative names for mapping
    const COLUMN_ALIASES = {
        'Date': ['date', 'order date', 'transaction date', 'day', 'time'],
        'OrderID': ['order id', 'order_id', 'transaction id', 'id', 'invoice'],
        'Category': ['category', 'course category', 'stream', 'dept', 'department'],
        'Batch': ['batch', 'batch name', 'course', 'class', 'group'],
        'Teacher': ['teacher', 'instructor', 'faculty', 'mentor', 'trainer'],
        'State': ['state', 'region', 'location', 'city', 'province'],
        'Sales': ['sales', 'revenue', 'amount', 'price', 'sales amount', 'total', 'gross revenue'],
        'Admissions': ['admissions', 'enrollments', 'students', 'quantity', 'qty', 'count'],
        'RefundAmount': ['refundamount', 'refund amount', 'refunded', 'refunded amount', 'refund'],
        'Month': ['month', 'target month', 'period', 'year-month'],
        'Target': ['target', 'monthly target', 'goal', 'quota'],
        'Capacity': ['capacity', 'max seats', 'seats', 'total seats'],
        'Profit': ['profit', 'margin', 'net profit', 'earnings']
    };

    // Global parsed workbook representation
    let parsedData = null;

    /**
     * Generate structured mock/demo data for instant BI preview
     */
    function generateDemoData() {
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(today.getDate() - 1);

        const formatDate = (d) => d.toISOString().split('T')[0];

        const categories = ['K-12 Academics', 'Coding & Tech', 'Creative Arts', 'Language Learning'];
        const teachers = ['Sarah Jenkins', 'David Chen', 'Aisha Rahman', 'Elena Petrova', 'Michael Brown'];
        const states = ['California', 'Texas', 'New York', 'Florida', 'Illinois'];
        const batches = [
            { name: 'Python Pro 101', category: 'Coding & Tech', teacher: 'David Chen', capacity: 50 },
            { name: 'Algebra Bootcamp', category: 'K-12 Academics', teacher: 'Sarah Jenkins', capacity: 40 },
            { name: 'Creative Writing', category: 'Creative Arts', teacher: 'Elena Petrova', capacity: 30 },
            { name: 'Advanced Spanish', category: 'Language Learning', teacher: 'Aisha Rahman', capacity: 25 },
            { name: 'Web Dev Mastery', category: 'Coding & Tech', teacher: 'David Chen', capacity: 60 },
            { name: 'AP Calculus Prep', category: 'K-12 Academics', teacher: 'Michael Brown', capacity: 35 }
        ];

        // Sales Mock
        const sales = [];
        let orderCounter = 10001;

        // Generate sales data for the last 30 days
        for (let i = 29; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(today.getDate() - i);
            const isToday = i === 0;
            const isYesterday = i === 1;

            // Vary sales volume per day (lower on weekends, random trends)
            const dayOfWeek = date.getDay();
            const volumeMultiplier = (dayOfWeek === 0 || dayOfWeek === 6) ? 0.6 : 1.0;
            const salesCount = Math.floor((15 + Math.random() * 20) * volumeMultiplier);

            for (let j = 0; j < salesCount; j++) {
                const batchObj = batches[Math.floor(Math.random() * batches.length)];
                const state = states[Math.floor(Math.random() * states.length)];
                const salePrice = batchObj.category === 'Coding & Tech' ? 250 + Math.random() * 100 : 120 + Math.random() * 50;

                sales.push({
                    Date: formatDate(date),
                    OrderID: `ORD-${orderCounter++}`,
                    Category: batchObj.category,
                    Batch: batchObj.name,
                    Teacher: batchObj.teacher,
                    State: state,
                    Sales: parseFloat(salePrice.toFixed(2)),
                    Admissions: 1
                });
            }
        }

        // Refunds Mock
        const refunds = [];
        // ~5% refund rate
        sales.forEach(sale => {
            if (sale.Date !== formatDate(today) && Math.random() < 0.05) {
                refunds.push({
                    Date: sale.Date,
                    OrderID: sale.OrderID,
                    RefundAmount: sale.Sales,
                    Category: sale.Category,
                    Batch: sale.Batch,
                    Teacher: sale.Teacher,
                    State: sale.State
                });
            }
        });

        // Targets Mock
        const currentMonthStr = formatDate(today).substring(0, 7); // YYYY-MM
        const targets = categories.map(cat => {
            let targetVal = 15000;
            if (cat === 'Coding & Tech') targetVal = 45000;
            if (cat === 'K-12 Academics') targetVal = 30000;
            return {
                Month: currentMonthStr,
                Category: cat,
                Target: targetVal
            };
        });

        // Batches Mock with filled admissions calculated
        const batchesData = batches.map(b => {
            const batchSales = sales.filter(s => s.Batch === b.name);
            const batchRefundsCount = refunds.filter(r => r.Batch === b.name).length;
            const netAdmissions = batchSales.length - batchRefundsCount;
            const profitVal = parseFloat((batchSales.reduce((acc, curr) => acc + curr.Sales, 0) * 0.45).toFixed(2)); // 45% margin

            return {
                Batch: b.name,
                Capacity: b.capacity,
                Teacher: b.teacher,
                Profit: profitVal
            };
        });

        return { sales, refunds, targets, batches: batchesData };
    }

    /**
     * Map CSV or Sheet headers automatically using aliases
     */
    function autoMapHeaders(headers, targetFields) {
        const mapping = {};
        targetFields.forEach(field => {
            const aliases = COLUMN_ALIASES[field] || [field.toLowerCase()];
            const matchedHeader = headers.find(h => {
                const cleanedHeader = h.toLowerCase().trim().replace(/[\s_\-]/g, '');
                return aliases.some(alias => {
                    const cleanedAlias = alias.toLowerCase().replace(/[\s_\-]/g, '');
                    return cleanedHeader === cleanedAlias || cleanedHeader.includes(cleanedAlias);
                });
            });
            if (matchedHeader) {
                mapping[field] = matchedHeader;
            }
        });
        return mapping;
    }

    /**
     * Parse File (.xlsx or .csv) uploaded by user
     */
    function parseFile(file, onComplete) {
        const reader = new FileReader();

        reader.onload = function (e) {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                
                let salesData = [];
                let refundData = [];
                let targetData = [];
                let batchData = [];

                // Attempt to identify sheets by names
                workbook.SheetNames.forEach(sheetName => {
                    const ws = workbook.Sheets[sheetName];
                    const json = XLSX.utils.sheet_to_json(ws);
                    if (json.length === 0) return;

                    const lowerName = sheetName.toLowerCase();
                    if (lowerName.includes('sale') || lowerName.includes('transaction')) {
                        salesData = json;
                    } else if (lowerName.includes('refund')) {
                        refundData = json;
                    } else if (lowerName.includes('target')) {
                        targetData = json;
                    } else if (lowerName.includes('batch') || lowerName.includes('course')) {
                        batchData = json;
                    }
                });

                // Fallback: If single sheet uploaded, treat it as Sales and generate others
                if (workbook.SheetNames.length === 1 && salesData.length === 0) {
                    const ws = workbook.Sheets[workbook.SheetNames[0]];
                    salesData = XLSX.utils.sheet_to_json(ws);
                }

                // If absolutely no sales data, fail
                if (salesData.length === 0) {
                    alert("Unable to parse Sales data. Make sure sheet names are clear (e.g. 'Sales', 'Refunds').");
                    return;
                }

                // Header mapping validation
                const sampleSalesRow = salesData[0];
                const salesHeaders = Object.keys(sampleSalesRow);
                const salesMap = autoMapHeaders(salesHeaders, EXPECTED_COLUMNS.sales);

                // Auto-fill any expected columns that are still missing with null/closest
                EXPECTED_COLUMNS.sales.forEach(field => {
                    if (!salesMap[field]) {
                        salesMap[field] = salesHeaders.find(h => h.toLowerCase().includes(field.toLowerCase())) || null;
                    }
                });

                finalizeData(salesData, refundData, targetData, batchData, salesMap, onComplete);
            } catch (err) {
                console.error("Error reading file: ", err);
                alert("Failed to parse Excel file. Ensure it is a valid .xlsx or .csv workbook.");
            }
        };

        reader.readAsArrayBuffer(file);
    }

    /**
     * Map headers to standard format and forward parsed workbook data
     */
    function finalizeData(salesRaw, refundsRaw, targetsRaw, batchesRaw, salesMap, onComplete) {
        const mappedSales = salesRaw.map((row, index) => {
            const mapped = {};
            Object.keys(salesMap).forEach(stdKey => {
                const userKey = salesMap[stdKey];
                mapped[stdKey] = (userKey && row[userKey] !== undefined) ? row[userKey] : null;
            });
            // Defaults/formatting for missing columns
            if (!mapped.Date) mapped.Date = new Date().toISOString().split('T')[0];
            if (!mapped.OrderID) mapped.OrderID = `TRX-${10000 + index}`;
            if (!mapped.Category) mapped.Category = 'General';
            if (!mapped.Batch) mapped.Batch = 'General Batch';
            if (!mapped.Teacher) mapped.Teacher = 'Instructor';
            if (!mapped.State) mapped.State = 'National';
            
            if (mapped.Sales !== null && mapped.Sales !== undefined) {
                mapped.Sales = parseFloat(mapped.Sales) || 0;
            } else {
                mapped.Sales = 0;
            }
            
            if (mapped.Admissions !== null && mapped.Admissions !== undefined) {
                mapped.Admissions = parseInt(mapped.Admissions) || 1;
            } else {
                mapped.Admissions = 1;
            }
            return mapped;
        });

        // Map refunds, targets, and batches with defaults if missing
        let mappedRefunds = [];
        if (refundsRaw.length > 0) {
            const refundHeaders = Object.keys(refundsRaw[0]);
            const refundsMap = autoMapHeaders(refundHeaders, EXPECTED_COLUMNS.refunds);
            mappedRefunds = refundsRaw.map(row => {
                const mapped = {};
                EXPECTED_COLUMNS.refunds.forEach(stdKey => {
                    const userKey = refundsMap[stdKey] || stdKey;
                    mapped[stdKey] = row[userKey] !== undefined ? row[userKey] : null;
                });
                if (mapped.RefundAmount) mapped.RefundAmount = parseFloat(mapped.RefundAmount);
                return mapped;
            });
        }

        let mappedTargets = [];
        if (targetsRaw.length > 0) {
            const targetHeaders = Object.keys(targetsRaw[0]);
            const targetsMap = autoMapHeaders(targetHeaders, EXPECTED_COLUMNS.targets);
            mappedTargets = targetsRaw.map(row => {
                const mapped = {};
                EXPECTED_COLUMNS.targets.forEach(stdKey => {
                    const userKey = targetsMap[stdKey] || stdKey;
                    mapped[stdKey] = row[userKey] !== undefined ? row[userKey] : null;
                });
                if (mapped.Target) mapped.Target = parseFloat(mapped.Target);
                return mapped;
            });
        } else {
            // Auto-create targets based on Sales Category sums
            const cats = [...new Set(mappedSales.map(s => s.Category))];
            const currentMonth = mappedSales[0]?.Date?.substring(0, 7) || new Date().toISOString().substring(0, 7);
            mappedTargets = cats.map(cat => {
                const catSalesTotal = mappedSales.filter(s => s.Category === cat).reduce((sum, item) => sum + item.Sales, 0);
                return {
                    Month: currentMonth,
                    Category: cat,
                    Target: Math.round(catSalesTotal * 0.9)
                };
            });
        }

        let mappedBatches = [];
        if (batchesRaw.length > 0) {
            const batchHeaders = Object.keys(batchesRaw[0]);
            const batchesMap = autoMapHeaders(batchHeaders, EXPECTED_COLUMNS.batches);
            mappedBatches = batchesRaw.map(row => {
                const mapped = {};
                EXPECTED_COLUMNS.batches.forEach(stdKey => {
                    const userKey = batchesMap[stdKey] || stdKey;
                    mapped[stdKey] = row[userKey] !== undefined ? row[userKey] : null;
                });
                if (mapped.Capacity) mapped.Capacity = parseInt(mapped.Capacity) || 40;
                if (mapped.Profit) mapped.Profit = parseFloat(mapped.Profit);
                return mapped;
            });
        } else {
            // Build batch data automatically
            const uniqueBatches = [...new Set(mappedSales.map(s => s.Batch))];
            mappedBatches = uniqueBatches.map(bName => {
                const sampleRow = mappedSales.find(s => s.Batch === bName);
                const batchSales = mappedSales.filter(s => s.Batch === bName).reduce((sum, item) => sum + item.Sales, 0);
                return {
                    Batch: bName,
                    Capacity: 50,
                    Teacher: sampleRow ? sampleRow.Teacher : 'Unknown Teacher',
                    Profit: parseFloat((batchSales * 0.45).toFixed(2))
                };
            });
        }

        parsedData = {
            sales: mappedSales,
            refunds: mappedRefunds,
            targets: mappedTargets,
            batches: mappedBatches
        };

        onComplete(parsedData);
    }

    /**
     * Download standard multi-sheet Excel template
     */
    function downloadTemplate() {
        const demo = generateDemoData();

        const wb = XLSX.utils.book_new();

        const wsSales = XLSX.utils.json_to_sheet(demo.sales);
        XLSX.utils.book_append_sheet(wb, wsSales, "Sales");

        const wsRefunds = XLSX.utils.json_to_sheet(demo.refunds);
        XLSX.utils.book_append_sheet(wb, wsRefunds, "Refunds");

        const wsTargets = XLSX.utils.json_to_sheet(demo.targets);
        XLSX.utils.book_append_sheet(wb, wsTargets, "Targets");

        const wsBatches = XLSX.utils.json_to_sheet(demo.batches);
        XLSX.utils.book_append_sheet(wb, wsBatches, "Batches");

        XLSX.writeFile(wb, "BI_Dashboard_Template.xlsx");
    }

    return {
        parseFile,
        generateDemoData,
        downloadTemplate,
        getLoadedData: () => parsedData,
        setLoadedData: (data) => { parsedData = data; }
    };
})();
