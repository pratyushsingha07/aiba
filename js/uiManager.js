/**
 * UI Manager Module
 * Manages DOM updates, Chart rendering, Business Insights generation, and Filter callbacks.
 */

window.UiManager = (function () {
    let activeTab = 'executive-summary';
    let chartInstances = {};

    // Helper to format currency
    function formatCurrency(val) {
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
    }

    // Helper to format percentages
    function formatPercent(val) {
        return `${val.toFixed(1)}%`;
    }

    /**
     * Set up all click handlers and navigation elements
     */
    function init(onFilterChanged) {
        // Tab navigation
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                this.classList.add('active');
                activeTab = this.dataset.tab;
                document.getElementById(activeTab).classList.add('active');

                // Resize charts if needed on tab switch
                triggerChartResize();
            });
        });

        // Setup filter listeners
        ['category', 'batch', 'teacher', 'state'].forEach(filterId => {
            document.getElementById(`filter-${filterId}`).addEventListener('change', onFilterChanged);
        });

        // Theme Switcher
        const themeBtn = document.getElementById('theme-toggle');
        themeBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            themeBtn.innerHTML = newTheme === 'light' ? '🌙' : '☀️';
            
            // Re-render charts to adjust text color for theme
            onFilterChanged();
        });

        // Comparison mode elements
        const compCheckbox = document.getElementById('compare-mode-toggle');
        const selectors = document.querySelector('.comparison-selectors');
        compCheckbox.addEventListener('change', function () {
            if (this.checked) {
                selectors.classList.add('active');
            } else {
                selectors.classList.remove('active');
            }
            onFilterChanged();
        });

        document.getElementById('compare-batch-a').addEventListener('change', onFilterChanged);
        document.getElementById('compare-batch-b').addEventListener('change', onFilterChanged);
    }

    /**
     * Populate filter dropdowns with unique options from parsed data, applying cascades
     */
    function populateFilters(data, activeFilters = {}) {
        const selectedCategory = activeFilters.category || 'All';
        const selectedBatch = activeFilters.batch || 'All';
        const selectedTeacher = activeFilters.teacher || 'All';
        const selectedState = activeFilters.state || 'All';

        // 1. Categories - Always all unique categories from data
        const categories = ['All', ...new Set(data.sales.map(s => s.Category))];

        // 2. Batches - Filtered by category
        let salesForCategory = data.sales;
        if (selectedCategory !== 'All') {
            salesForCategory = data.sales.filter(s => s.Category === selectedCategory);
        }
        const batches = ['All', ...new Set(salesForCategory.map(s => s.Batch))];

        // 3. Teachers - Filtered by category and batch
        let salesForBatch = salesForCategory;
        if (selectedBatch !== 'All') {
            salesForBatch = salesForCategory.filter(s => s.Batch === selectedBatch);
        }
        const teachers = ['All', ...new Set(salesForBatch.map(s => s.Teacher))];

        // 4. States - Filtered by category, batch, and teacher
        let salesForTeacher = salesForBatch;
        if (selectedTeacher !== 'All') {
            salesForTeacher = salesForBatch.filter(s => s.Teacher === selectedTeacher);
        }
        const states = ['All', ...new Set(salesForTeacher.map(s => s.State))];

        const populateSelect = (id, list, currentValue) => {
            const select = document.getElementById(id);
            select.innerHTML = '';
            list.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item;
                opt.textContent = item;
                select.appendChild(opt);
            });
            // Restore previous selection if still available, otherwise default to All
            if (list.includes(currentValue)) {
                select.value = currentValue;
            } else {
                select.value = 'All';
            }
        };

        populateSelect('filter-category', categories, selectedCategory);
        populateSelect('filter-batch', batches, selectedBatch);
        populateSelect('filter-teacher', teachers, selectedTeacher);
        populateSelect('filter-state', states, selectedState);

        // Populate comparison options
        const batchA = document.getElementById('compare-batch-a');
        const batchB = document.getElementById('compare-batch-b');
        const currentA = batchA.value;
        const currentB = batchB.value;

        batchA.innerHTML = '';
        batchB.innerHTML = '';
        const allBatches = ['All', ...new Set(data.sales.map(s => s.Batch))].filter(b => b !== 'All');

        allBatches.forEach(bName => {
            const optA = document.createElement('option');
            optA.value = bName;
            optA.textContent = bName;
            batchA.appendChild(optA);

            const optB = document.createElement('option');
            optB.value = bName;
            optB.textContent = bName;
            batchB.appendChild(optB);
        });

        if (allBatches.includes(currentA)) {
            batchA.value = currentA;
        }
        if (allBatches.includes(currentB)) {
            batchB.value = currentB;
        } else if (allBatches.length > 1) {
            batchB.selectedIndex = 1;
        }
    }

    /**
     * Render the UI with calculated metrics and performance
     */
    function renderDashboard(kpis, filteredData, originalData) {
        document.querySelector('main').style.display = 'block';

        // 1. Render KPI Cards
        renderKpiCards(kpis);

        // 2. Render Section-specific Tables & Visuals
        renderExecutiveSummary(kpis, filteredData);
        renderSalesDashboard(filteredData);
        renderTargetDashboard(kpis, filteredData);
        renderBatchDashboard(filteredData);
        renderCategoryDashboard(filteredData);
        renderTeacherDashboard(filteredData);
        renderStateDashboard(filteredData);
        renderRefundDashboard(kpis, filteredData);
        renderForecastDashboard(kpis, filteredData);
        renderBusinessInsights(kpis, filteredData);

        // 3. Render Comparison table if active
        renderComparisonSection(originalData);
    }

    /**
     * Render KPI cards on page
     */
    function renderKpiCards(kpis) {
        // Today's Sales Card
        const todayTrend = kpis.todaySales >= kpis.yesterdaySales ? 'up' : 'down';
        const todayPct = kpis.yesterdaySales > 0 ? ((kpis.todaySales - kpis.yesterdaySales) / kpis.yesterdaySales) * 100 : 0;
        document.getElementById('kpi-today-sales').innerHTML = `
            <div class="kpi-label">Today's Sales</div>
            <div class="kpi-value">${formatCurrency(kpis.todaySales)}</div>
            <div class="kpi-trend trend-${todayTrend}">
                ${todayTrend === 'up' ? '▲' : '▼'} ${formatPercent(Math.abs(todayPct))} vs Yesterday
            </div>
        `;

        // Monthly Target Card
        document.getElementById('kpi-target').innerHTML = `
            <div class="kpi-label">Target Progress</div>
            <div class="kpi-value">${formatPercent(kpis.targetAchievedPercent)}</div>
            <div class="kpi-trend trend-neutral">
                Target: ${formatCurrency(kpis.totalTarget)}
            </div>
        `;

        // Revenue Card
        const growthTrend = kpis.momGrowth >= 0 ? 'up' : 'down';
        document.getElementById('kpi-revenue').innerHTML = `
            <div class="kpi-label">Gross Revenue</div>
            <div class="kpi-value">${formatCurrency(kpis.grossRevenue)}</div>
            <div class="kpi-trend trend-${growthTrend}">
                ${growthTrend === 'up' ? '▲' : '▼'} ${formatPercent(Math.abs(kpis.momGrowth))} Growth
            </div>
        `;

        // Profit Card
        document.getElementById('kpi-profit').innerHTML = `
            <div class="kpi-label">Batch Profit</div>
            <div class="kpi-value">${formatCurrency(kpis.profit)}</div>
            <div class="kpi-trend trend-neutral">
                Avg Order Value: ${formatCurrency(kpis.averageSellingPrice)}
            </div>
        `;
    }

    /**
     * Section details
     */
    function renderExecutiveSummary(kpis, filteredData) {
        // Build Recent sales table
        const tbody = document.getElementById('recent-sales-table');
        tbody.innerHTML = '';
        
        // Take last 8 records
        const recent = filteredData.sales.slice(-8).reverse();
        recent.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.Date}</td>
                <td>${row.OrderID}</td>
                <td>${row.Category}</td>
                <td>${row.Batch}</td>
                <td>${row.Teacher}</td>
                <td>${formatCurrency(row.Sales)}</td>
            `;
            tbody.appendChild(tr);
        });

        // Top Performers List (Batches)
        const batchPerf = KpiEngine.getBatchPerformance(filteredData).slice(0, 5);
        const topPerfContainer = document.getElementById('top-performers-mini');
        topPerfContainer.innerHTML = '';
        batchPerf.forEach(b => {
            const div = document.createElement('div');
            div.style.display = 'flex';
            div.style.justifyContent = 'space-between';
            div.style.padding = '0.5rem 0';
            div.style.borderBottom = '1px solid var(--border-color)';
            div.innerHTML = `
                <span style="font-weight:500;">${b.batch}</span>
                <span class="trend-up">${formatCurrency(b.revenue)}</span>
            `;
            topPerfContainer.appendChild(div);
        });

        // Quick charts inside Executive Summary
        renderChart('sales-overview-chart', 'bar', getSalesTrendData(filteredData.sales));
    }

    function renderSalesDashboard(filteredData) {
        const salesData = getSalesTrendData(filteredData.sales);
        renderChart('sales-trend-chart', 'line', salesData);
        renderChart('orders-trend-chart', 'bar', getOrdersTrendData(filteredData.sales));
    }

    function renderTargetDashboard(kpis, filteredData) {
        // Target versus achieved comparison
        const categories = [...new Set(filteredData.targets.map(t => t.Category))];
        const achieved = categories.map(cat => {
            return filteredData.sales.filter(s => s.Category === cat).reduce((acc, s) => acc + s.Sales, 0);
        });
        const targets = categories.map(cat => {
            return filteredData.targets.filter(t => t.Category === cat).reduce((acc, t) => acc + t.Target, 0);
        });

        const data = {
            labels: categories,
            datasets: [
                {
                    label: 'Achieved Revenue',
                    data: achieved,
                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    borderColor: '#10b981',
                    borderWidth: 1
                },
                {
                    label: 'Target Revenue',
                    data: targets,
                    backgroundColor: 'rgba(59, 130, 246, 0.3)',
                    borderColor: '#3b82f6',
                    borderWidth: 1
                }
            ]
        };

        renderChart('target-comparison-chart', 'bar', data);
        
        // Progress Table
        const tbody = document.getElementById('target-table-body');
        tbody.innerHTML = '';
        categories.forEach((cat, idx) => {
            const ach = achieved[idx];
            const trg = targets[idx];
            const pct = trg > 0 ? (ach / trg) * 100 : 0;
            const diff = trg - ach;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${cat}</td>
                <td>${formatCurrency(trg)}</td>
                <td>${formatCurrency(ach)}</td>
                <td><span style="font-weight: 600;" class="${pct >= 100 ? 'trend-up' : 'trend-down'}">${formatPercent(pct)}</span></td>
                <td>${diff <= 0 ? '<span class="trend-up">Achieved</span>' : formatCurrency(diff)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderBatchDashboard(filteredData) {
        const perf = KpiEngine.getBatchPerformance(filteredData);
        
        // Render Charts
        const top10 = perf.slice(0, 10);
        const bottom10 = [...perf].reverse().slice(0, 10);

        renderChart('top-batches-chart', 'bar', {
            labels: top10.map(b => b.batch),
            datasets: [{
                label: 'Revenue',
                data: top10.map(b => b.revenue),
                backgroundColor: 'rgba(59, 130, 246, 0.85)'
            }]
        });

        renderChart('bottom-batches-chart', 'bar', {
            labels: bottom10.map(b => b.batch),
            datasets: [{
                label: 'Revenue',
                data: bottom10.map(b => b.revenue),
                backgroundColor: 'rgba(239, 68, 68, 0.85)'
            }]
        });

        // Table
        const tbody = document.getElementById('batch-table-body');
        tbody.innerHTML = '';
        perf.forEach(b => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${b.batch}</td>
                <td>${formatCurrency(b.revenue)}</td>
                <td>${b.admissions} / ${b.capacity}</td>
                <td><span style="font-weight:600;">${formatPercent(b.fillPercent)}</span></td>
                <td>${formatCurrency(b.profit)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderCategoryDashboard(filteredData) {
        const perf = KpiEngine.getCategoryPerformance(filteredData);
        renderChart('category-comparison-chart', 'doughnut', {
            labels: perf.map(c => c.category),
            datasets: [{
                data: perf.map(c => c.revenue),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
            }]
        });

        // Table
        const tbody = document.getElementById('category-table-body');
        tbody.innerHTML = '';
        perf.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${c.category}</td>
                <td>${formatCurrency(c.revenue)}</td>
                <td>${c.orders}</td>
                <td>${formatCurrency(c.profit)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderTeacherDashboard(filteredData) {
        const perf = KpiEngine.getTeacherPerformance(filteredData);
        renderChart('teacher-performance-chart', 'bar', {
            labels: perf.map(t => t.teacher),
            datasets: [{
                label: 'Revenue Generated',
                data: perf.map(t => t.revenue),
                backgroundColor: 'rgba(139, 92, 246, 0.85)'
            }]
        }, { indexAxis: 'y' });

        const tbody = document.getElementById('teacher-table-body');
        tbody.innerHTML = '';
        perf.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${t.teacher}</td>
                <td>${formatCurrency(t.revenue)}</td>
                <td>${t.admissions}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderStateDashboard(filteredData) {
        const perf = KpiEngine.getStatePerformance(filteredData);
        renderChart('state-performance-chart', 'pie', {
            labels: perf.map(s => s.state),
            datasets: [{
                data: perf.map(s => s.revenue),
                backgroundColor: ['#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b']
            }]
        });

        const tbody = document.getElementById('state-table-body');
        tbody.innerHTML = '';
        perf.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${s.state}</td>
                <td>${formatCurrency(s.revenue)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderRefundDashboard(kpis, filteredData) {
        // Group refunds by category
        const cats = [...new Set(filteredData.refunds.map(r => r.Category))];
        const amounts = cats.map(cat => filteredData.refunds.filter(r => r.Category === cat).reduce((sum, r) => sum + r.RefundAmount, 0));

        renderChart('refund-trend-chart', 'doughnut', {
            labels: cats.length > 0 ? cats : ['No Refunds'],
            datasets: [{
                data: amounts.length > 0 ? amounts : [0],
                backgroundColor: ['#ef4444', '#f59e0b', '#ec4899', '#8b5cf6']
            }]
        });

        // Detailed Refund Table
        const tbody = document.getElementById('refunds-table-body');
        tbody.innerHTML = '';
        filteredData.refunds.slice(-10).reverse().forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${r.Date}</td>
                <td>${r.OrderID}</td>
                <td>${r.Category}</td>
                <td>${r.Batch}</td>
                <td>${formatCurrency(r.RefundAmount)}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderForecastDashboard(kpis, filteredData) {
        // Generate linear forecast projection for next 7 days
        const salesTrend = getSalesTrendData(filteredData.sales);
        const labels = [...salesTrend.labels];
        const dataPoints = [...salesTrend.datasets[0].data];

        // Add 7 forecast days
        const lastDate = new Date(labels[labels.length - 1]);
        const forecastLabels = [...labels];
        const actualsData = [...dataPoints];
        const forecastData = Array(dataPoints.length - 1).fill(null);
        forecastData.push(dataPoints[dataPoints.length - 1]); // connect forecast line

        for (let i = 1; i <= 7; i++) {
            const nextDate = new Date(lastDate);
            nextDate.setDate(lastDate.getDate() + i);
            forecastLabels.push(nextDate.toISOString().split('T')[0]);
            // Projection is linear run rate with 5% variance
            const projection = kpis.dailyRunRate * (1 + (Math.random() - 0.5) * 0.1);
            forecastData.push(parseFloat(projection.toFixed(2)));
            actualsData.push(null);
        }

        renderChart('forecast-trend-chart', 'line', {
            labels: forecastLabels,
            datasets: [
                {
                    label: 'Actual Sales',
                    data: actualsData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true
                },
                {
                    label: 'Forecast Sales',
                    data: forecastData,
                    borderColor: '#f59e0b',
                    borderDash: [5, 5],
                    backgroundColor: 'transparent'
                }
            ]
        });

        // Forecast summary statistics
        document.getElementById('forecast-summary-box').innerHTML = `
            <div class="insight-block warning">
                <h4>Linear Run-Rate Forecasting Model</h4>
                <p>Based on the computed <strong>Daily Run Rate (${formatCurrency(kpis.dailyRunRate)})</strong>:</p>
                <ul>
                    <li>Expected Month-End Revenue: <strong>${formatCurrency(kpis.expectedMonthRevenue)}</strong></li>
                    <li>Expected Target Achievement Rate: <strong>${formatPercent(kpis.forecastTargetAchievement)}</strong></li>
                    <li>Required Daily Run Rate to meet Target: <strong>${formatCurrency(kpis.requiredDRR)}</strong></li>
                </ul>
            </div>
        `;
    }

    function renderBusinessInsights(kpis, filteredData) {
        const topBatches = KpiEngine.getBatchPerformance(filteredData).slice(0, 3);
        const bottomBatches = KpiEngine.getBatchPerformance(filteredData).reverse().slice(0, 3);
        
        // Dynamic calculations for insights
        const categories = KpiEngine.getCategoryPerformance(filteredData);
        const bestCategory = categories[0] || { category: 'N/A', revenue: 0 };
        const bestCatShare = kpis.grossRevenue > 0 ? (bestCategory.revenue / kpis.grossRevenue) * 100 : 0;

        const teachers = KpiEngine.getTeacherPerformance(filteredData);
        const bestTeacher = teachers[0] || { teacher: 'N/A', admissions: 0 };

        // Low occupancy batches (fillPercent < 50)
        const lowOccupancyBatches = KpiEngine.getBatchPerformance(filteredData).filter(b => b.fillPercent < 50);

        // Target shortfall logic
        const targetStatus = kpis.forecastTargetAchievement >= 100 ? 'On Track' : 'At Risk';
        const projectedShortfall = Math.max(0, kpis.totalTarget - kpis.expectedMonthRevenue);

        const container = document.getElementById('insights-container');
        container.innerHTML = `
            <div class="insight-block ${targetStatus === 'On Track' ? 'success' : 'danger'}">
                <h4>Executive Summary & Target Progress Status: <span style="text-decoration: underline;">${targetStatus}</span></h4>
                <p>The business is currently operating at a Daily Run Rate of <strong>${formatCurrency(kpis.dailyRunRate)}</strong>. Net Revenue stands at <strong>${formatCurrency(kpis.netRevenue)}</strong> with a target achievement progress of <strong>${formatPercent(kpis.targetAchievedPercent)}</strong>.
                ${targetStatus === 'On Track' 
                    ? `Our current linear forecast indicates we are on track to exceed our target, reaching <strong>${formatPercent(kpis.forecastTargetAchievement)}</strong> of our goal.` 
                    : `We project a month-end shortfall of <strong>${formatCurrency(projectedShortfall)}</strong> (reaching <strong>${formatPercent(kpis.forecastTargetAchievement)}</strong> of target) unless the Daily Run Rate is increased.`}</p>
            </div>

            <div class="insight-block success">
                <h4>Top Performers (Batches & Categories)</h4>
                <ul>
                    ${topBatches.map(b => `<li><strong>${b.batch}</strong> leads the growth table, generating a total revenue of <strong>${formatCurrency(b.revenue)}</strong> with a fill occupancy rate of <strong>${formatPercent(b.fillPercent)}</strong>.</li>`).join('')}
                    <li><strong>${bestCategory.category}</strong> is the top performing vertical, bringing in <strong>${formatCurrency(bestCategory.revenue)}</strong>, which represents <strong>${formatPercent(bestCatShare)}</strong> of gross sales.</li>
                    <li><strong>${bestTeacher.teacher}</strong> generated the most student enrollment with <strong>${bestTeacher.admissions}</strong> total admissions.</li>
                </ul>
            </div>

            <div class="insight-block danger">
                <h4>Underperforming Sections & Risk Analysis</h4>
                <ul>
                    ${bottomBatches.map(b => `<li><strong>${b.batch}</strong> requires attention; occupancy is at <strong>${formatPercent(b.fillPercent)}</strong> generating revenue of only <strong>${formatCurrency(b.revenue)}</strong>.</li>`).join('')}
                    ${lowOccupancyBatches.length > 0 ? `<li><strong>${lowOccupancyBatches.length} batches</strong> are operating under 50% capacity, indicating low class utilization.</li>` : ''}
                    ${kpis.refundPercent > 8 ? `<li>High refund rate detected at <strong>${formatPercent(kpis.refundPercent)}</strong>, resulting in a loss of <strong>${formatCurrency(kpis.refundAmount)}</strong>. Check student satisfaction or curriculum feedback.</li>` : ''}
                </ul>
            </div>

            <div class="insight-block warning">
                <h4>Strategic Business Recommendations</h4>
                <ul>
                    <li>Scale marketing spend and add seat allocation to high occupancy batches like <strong>${topBatches[0]?.batch || 'Top Batches'}</strong>.</li>
                    <li>To meet the monthly revenue targets, ensure sales operations maintains a run rate above <strong>${formatCurrency(kpis.requiredDRR)}</strong> (current rate is <strong>${formatCurrency(kpis.dailyRunRate)}</strong>).</li>
                    ${projectedShortfall > 0 ? `<li>Target Category Manager intervention is required to close the projected <strong>${formatCurrency(projectedShortfall)}</strong> gap. Focus on upselling current students in <strong>${bestCategory.category}</strong>.</li>` : ''}
                </ul>
            </div>
        `;
    }

    function renderComparisonSection(originalData) {
        const isEnabled = document.getElementById('compare-mode-toggle').checked;
        const compareCard = document.getElementById('comparison-card-container');

        if (!isEnabled) {
            compareCard.style.display = 'none';
            return;
        }

        compareCard.style.display = 'block';
        const batchA = document.getElementById('compare-batch-a').value;
        const batchB = document.getElementById('compare-batch-b').value;

        const results = KpiEngine.compareBatches(originalData, batchA, batchB);

        const tbody = document.getElementById('comparison-table-body');
        tbody.innerHTML = '';

        results.forEach(row => {
            const isPct = row.format === 'percent';
            const isCurr = row.format === 'currency';

            const formatVal = (v) => {
                if (isPct) return formatPercent(v);
                if (isCurr) return formatCurrency(v);
                return v;
            };

            const trendClass = row.diff >= 0 ? 'trend-up' : 'trend-down';
            const trendSymbol = row.diff >= 0 ? '+' : '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${row.metric}</strong></td>
                <td>${formatVal(row.valA)}</td>
                <td>${formatVal(row.valB)}</td>
                <td class="${trendClass}">${trendSymbol}${formatVal(row.diff)}</td>
                <td class="${trendClass}">${trendSymbol}${row.pctDiff.toFixed(1)}%</td>
            `;
            tbody.appendChild(tr);
        });
    }

    /**
     * Chart.js wrappers
     */
    function renderChart(canvasId, type, data, options = {}) {
        const canvas = document.getElementById(canvasId);
        const ctx = canvas.getContext('2d');

        // Check if theme requires different colors
        const theme = document.documentElement.getAttribute('data-theme') || 'dark';
        const gridColor = theme === 'light' ? 'rgba(15, 23, 42, 0.05)' : 'rgba(255, 255, 255, 0.05)';
        const textColor = theme === 'light' ? '#64748b' : '#94a3b8';

        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
        }

        // Apply custom gradient styling to datasets
        if (data.datasets && data.datasets.length > 0) {
            data.datasets.forEach((dataset) => {
                const primaryColor = dataset.borderColor || dataset.backgroundColor || '#3b82f6';
                const baseColor = typeof primaryColor === 'string' ? primaryColor : '#3b82f6';
                
                if (type === 'line') {
                    if (dataset.tension === undefined) {
                        dataset.tension = 0.45;
                    }
                    dataset.borderWidth = dataset.borderWidth || 3;
                    dataset.pointRadius = dataset.pointRadius || 2;
                    dataset.pointHoverRadius = dataset.pointHoverRadius || 5;
                    
                    if (dataset.fill) {
                        const grad = ctx.createLinearGradient(0, 0, 0, 300);
                        grad.addColorStop(0, hexToRgba(baseColor, 0.35));
                        grad.addColorStop(1, hexToRgba(baseColor, 0.0));
                        dataset.backgroundColor = grad;
                    }
                } else if (type === 'bar') {
                    const grad = ctx.createLinearGradient(0, 0, 0, 300);
                    grad.addColorStop(0, hexToRgba(baseColor, 0.85));
                    grad.addColorStop(1, hexToRgba(baseColor, 0.2));
                    dataset.backgroundColor = grad;
                    dataset.borderRadius = 5;
                }
            });
        }

        const standardOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { 
                        color: textColor,
                        font: { family: 'Plus Jakarta Sans', weight: '600', size: 11 } 
                    }
                },
                tooltip: {
                    backgroundColor: theme === 'light' ? '#ffffff' : '#090d16',
                    titleColor: theme === 'light' ? '#0f172a' : '#ffffff',
                    bodyColor: theme === 'light' ? '#475569' : '#94a3b8',
                    borderColor: theme === 'light' ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    bodyFont: { family: 'Plus Jakarta Sans' },
                    titleFont: { family: 'Outfit', weight: '700' }
                }
            },
            scales: type !== 'doughnut' && type !== 'pie' ? {
                x: { 
                    grid: { color: gridColor, drawBorder: false }, 
                    ticks: { color: textColor, font: { family: 'Plus Jakarta Sans', size: 10 } } 
                },
                y: { 
                    grid: { color: gridColor, drawBorder: false }, 
                    ticks: { color: textColor, font: { family: 'Plus Jakarta Sans', size: 10 } } 
                }
            } : {}
        };

        const mergedOptions = { ...standardOptions, ...options };
        if (options.plugins) mergedOptions.plugins = { ...standardOptions.plugins, ...options.plugins };

        chartInstances[canvasId] = new Chart(ctx, {
            type: type,
            data: data,
            options: mergedOptions
        });
    }

    // Helper to convert hex to rgba
    function hexToRgba(hex, alpha) {
        if (typeof hex !== 'string' || !hex.startsWith('#')) return hex;
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    function triggerChartResize() {
        setTimeout(() => {
            Object.values(chartInstances).forEach(chart => {
                chart.resize();
            });
        }, 100);
    }

    /**
     * Data processing helper for chart structures
     */
    function getSalesTrendData(sales) {
        // Group sales by date
        const grouped = {};
        sales.forEach(s => {
            grouped[s.Date] = (grouped[s.Date] || 0) + s.Sales;
        });
        const labels = Object.keys(grouped).sort();
        const data = labels.map(l => grouped[l]);

        return {
            labels,
            datasets: [{
                label: 'Sales Revenue',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                fill: true,
                tension: 0.1
            }]
        };
    }

    function getOrdersTrendData(sales) {
        const grouped = {};
        sales.forEach(s => {
            grouped[s.Date] = (grouped[s.Date] || 0) + 1;
        });
        const labels = Object.keys(grouped).sort();
        const data = labels.map(l => grouped[l]);

        return {
            labels,
            datasets: [{
                label: 'Order Count',
                data: data,
                backgroundColor: 'rgba(16, 185, 129, 0.8)'
            }]
        };
    }

    return {
        init,
        populateFilters,
        renderDashboard,
        triggerChartResize
    };
})();
