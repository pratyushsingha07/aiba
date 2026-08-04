/**
 * KPI Engine Module
 * Computes all business metrics, aggregations, trend tables, and forecasting logic.
 */

window.KpiEngine = (function () {

    /**
     * Filter the datasets based on active controls
     */
    function filterData(data, filters) {
        if (!data) return null;

        let sales = [...data.sales];
        let refunds = [...data.refunds];
        let targets = [...data.targets];
        let batches = [...data.batches];

        if (filters.category && filters.category !== 'All') {
            sales = sales.filter(s => s.Category === filters.category);
            refunds = refunds.filter(r => r.Category === filters.category);
            targets = targets.filter(t => t.Category === filters.category);
        }

        if (filters.batch && filters.batch !== 'All') {
            sales = sales.filter(s => s.Batch === filters.batch);
            refunds = refunds.filter(r => r.Batch === filters.batch);
            batches = batches.filter(b => b.Batch === filters.batch);
        }

        if (filters.teacher && filters.teacher !== 'All') {
            sales = sales.filter(s => s.Teacher === filters.teacher);
            refunds = refunds.filter(r => r.Teacher === filters.teacher);
            batches = batches.filter(b => b.Teacher === filters.teacher);
        }

        if (filters.state && filters.state !== 'All') {
            sales = sales.filter(s => s.State === filters.state);
            refunds = refunds.filter(r => r.State === filters.state);
        }

        return { sales, refunds, targets, batches };
    }

    /**
     * Calculate core KPIs for the filtered dataset
     */
    function calculateKPIs(filteredData) {
        const { sales, refunds, targets, batches } = filteredData;

        // Base metrics
        const totalGrossRevenue = sales.reduce((acc, s) => acc + s.Sales, 0);
        const totalRefundAmount = refunds.reduce((acc, r) => acc + r.RefundAmount, 0);
        const netRevenue = Math.max(0, totalGrossRevenue - totalRefundAmount);
        const refundPercent = totalGrossRevenue > 0 ? (totalRefundAmount / totalGrossRevenue) * 100 : 0;
        const totalOrders = sales.length;
        const averageSellingPrice = totalOrders > 0 ? totalGrossRevenue / totalOrders : 0;

        // Calculate Today's & Yesterday's Sales
        let todaySales = 0;
        let yesterdaySales = 0;
        const uniqueDates = [...new Set(sales.map(s => s.Date))].sort();

        if (uniqueDates.length > 0) {
            const maxDateStr = uniqueDates[uniqueDates.length - 1];
            todaySales = sales.filter(s => s.Date === maxDateStr).reduce((acc, s) => acc + s.Sales, 0);

            if (uniqueDates.length > 1) {
                const prevDateStr = uniqueDates[uniqueDates.length - 2];
                yesterdaySales = sales.filter(s => s.Date === prevDateStr).reduce((acc, s) => acc + s.Sales, 0);
            }
        }

        // Calculate exact calendar span of the dataset
        let daysInPeriod = 1;
        if (uniqueDates.length > 0) {
            const minDate = new Date(uniqueDates[0]);
            const maxDate = new Date(uniqueDates[uniqueDates.length - 1]);
            const diffTime = Math.abs(maxDate - minDate);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
            daysInPeriod = isNaN(diffDays) ? uniqueDates.length : diffDays;
        }

        // Daily Run Rate (DRR) over calendar span
        const dailyRunRate = totalGrossRevenue / (daysInPeriod || 1);

        // Growth metrics with safety checks
        let wowGrowth = 0;
        if (uniqueDates.length >= 14) {
            const last7Dates = uniqueDates.slice(-7);
            const prev7Dates = uniqueDates.slice(-14, -7);

            const last7Sales = sales.filter(s => last7Dates.includes(s.Date)).reduce((acc, s) => acc + s.Sales, 0);
            const prev7Sales = sales.filter(s => prev7Dates.includes(s.Date)).reduce((acc, s) => acc + s.Sales, 0);

            wowGrowth = prev7Sales > 0 ? ((last7Sales - prev7Sales) / prev7Sales) * 100 : 0;
        }

        let momGrowth = 0;
        if (uniqueDates.length >= 2) {
            const mid = Math.floor(uniqueDates.length / 2);
            const secondHalfDates = uniqueDates.slice(mid);
            const firstHalfDates = uniqueDates.slice(0, mid);

            const secondHalfSales = sales.filter(s => secondHalfDates.includes(s.Date)).reduce((acc, s) => acc + s.Sales, 0);
            const firstHalfSales = sales.filter(s => firstHalfDates.includes(s.Date)).reduce((acc, s) => acc + s.Sales, 0);

            momGrowth = firstHalfSales > 0 ? ((secondHalfSales - firstHalfSales) / firstHalfSales) * 100 : 0;
        }

        // Target progress calculations
        const totalTarget = targets.reduce((acc, t) => acc + t.Target, 0);
        const targetAchievedPercent = totalTarget > 0 ? (totalGrossRevenue / totalTarget) * 100 : 0;
        const targetRemaining = Math.max(0, totalTarget - totalGrossRevenue);

        // Days in month calculation dynamically determined from the last transaction
        let daysInMonth = 30;
        let daysPassed = 1;
        let daysRemaining = 29;
        if (uniqueDates.length > 0) {
            const lastDate = new Date(uniqueDates[uniqueDates.length - 1]);
            const year = lastDate.getFullYear();
            const month = lastDate.getMonth(); // 0-indexed
            daysInMonth = new Date(year, month + 1, 0).getDate(); // exact calendar days in month
            daysPassed = lastDate.getDate();
            daysRemaining = Math.max(1, daysInMonth - daysPassed);
        }

        const requiredDRR = targetRemaining / daysRemaining;

        // Forecast metrics based on dynamic month-end
        const expectedMonthRevenue = dailyRunRate * daysInMonth;
        const forecastTargetAchievement = totalTarget > 0 ? (expectedMonthRevenue / totalTarget) * 100 : 0;

        // Profit & Loss calculation (from batches or estimated)
        const profit = batches.reduce((acc, b) => acc + (b.Profit || 0), 0) || (netRevenue * 0.45);
        const loss = totalRefundAmount;

        return {
            grossRevenue: totalGrossRevenue,
            netRevenue,
            refundAmount: totalRefundAmount,
            refundPercent,
            orders: totalOrders,
            averageSellingPrice,
            todaySales,
            yesterdaySales,
            dailyRunRate,
            wowGrowth,
            momGrowth,
            totalTarget,
            targetAchievedPercent,
            targetRemaining,
            requiredDRR,
            expectedMonthRevenue,
            forecastTargetAchievement,
            profit,
            loss
        };
    }

    /**
     * Entity specific analysis generators
     */
    function getCategoryPerformance(filteredData) {
        const { sales } = filteredData;
        const categories = [...new Set(sales.map(s => s.Category))];
        return categories.map(cat => {
            const catSales = sales.filter(s => s.Category === cat);
            const revenue = catSales.reduce((acc, s) => acc + s.Sales, 0);
            const orders = catSales.length;
            const profit = parseFloat((revenue * 0.45).toFixed(2));
            return { category: cat, revenue, orders, profit };
        }).sort((a, b) => b.revenue - a.revenue);
    }

    function getBatchPerformance(filteredData) {
        const { sales, refunds, batches } = filteredData;
        const batchNames = [...new Set(sales.map(s => s.Batch))];

        return batchNames.map(bName => {
            const batchSales = sales.filter(s => s.Batch === bName);
            const batchRefunds = refunds.filter(r => r.Batch === bName);
            const revenue = batchSales.reduce((acc, s) => acc + s.Sales, 0);
            const refundAmount = batchRefunds.reduce((acc, r) => acc + r.RefundAmount, 0);
            const admissions = batchSales.length - batchRefunds.length;

            const batchObj = batches.find(b => b.Batch === bName) || { Capacity: 50, Profit: revenue * 0.45 };
            const fillPercent = batchObj.Capacity > 0 ? (admissions / batchObj.Capacity) * 100 : 0;

            return {
                batch: bName,
                revenue,
                admissions,
                capacity: batchObj.Capacity,
                fillPercent,
                profit: batchObj.Profit || (revenue - refundAmount) * 0.45,
                refundAmount
            };
        }).sort((a, b) => b.revenue - a.revenue);
    }

    function getTeacherPerformance(filteredData) {
        const { sales } = filteredData;
        const teachers = [...new Set(sales.map(s => s.Teacher))];
        return teachers.map(t => {
            const teacherSales = sales.filter(s => s.Teacher === t);
            const revenue = teacherSales.reduce((acc, s) => acc + s.Sales, 0);
            const admissions = teacherSales.length;
            return { teacher: t, revenue, admissions };
        }).sort((a, b) => b.revenue - a.revenue);
    }

    function getStatePerformance(filteredData) {
        const { sales } = filteredData;
        const states = [...new Set(sales.map(s => s.State))];
        return states.map(st => {
            const stateSales = sales.filter(s => s.State === st);
            const revenue = stateSales.reduce((acc, s) => acc + s.Sales, 0);
            return { state: st, revenue };
        }).sort((a, b) => b.revenue - a.revenue);
    }

    /**
     * Compute comparative metrics for two specific entities (e.g. Batch vs Batch)
     */
    function compareBatches(data, batchA, batchB) {
        const dataA = filterData(data, { batch: batchA });
        const dataB = filterData(data, { batch: batchB });

        const kpiA = calculateKPIs(dataA);
        const kpiB = calculateKPIs(dataB);

        const perfA = getBatchPerformance(dataA).find(b => b.batch === batchA) || {};
        const perfB = getBatchPerformance(dataB).find(b => b.batch === batchB) || {};

        const metrics = [
            { label: 'Sales Orders', valA: kpiA.orders, valB: kpiB.orders, format: 'num' },
            { label: 'Revenue', valA: kpiA.grossRevenue, valB: kpiB.grossRevenue, format: 'currency' },
            { label: 'Growth % (MoM)', valA: kpiA.momGrowth, valB: kpiB.momGrowth, format: 'percent' },
            { label: 'Refund %', valA: kpiA.refundPercent, valB: kpiB.refundPercent, format: 'percent' },
            { label: 'Profit', valA: kpiA.profit, valB: kpiB.profit, format: 'currency' },
            { label: 'Target Achievement %', valA: kpiA.targetAchievedPercent, valB: kpiB.targetAchievedPercent, format: 'percent' },
            { label: 'Batch Fill %', valA: perfA.fillPercent || 0, valB: perfB.fillPercent || 0, format: 'percent' }
        ];

        return metrics.map(m => {
            const diff = m.valA - m.valB;
            const pctDiff = m.valB > 0 ? (diff / m.valB) * 100 : 0;
            return {
                metric: m.label,
                valA: m.valA,
                valB: m.valB,
                diff,
                pctDiff,
                format: m.format
            };
        });
    }

    return {
        filterData,
        calculateKPIs,
        getCategoryPerformance,
        getBatchPerformance,
        getTeacherPerformance,
        getStatePerformance,
        compareBatches
    };
})();
