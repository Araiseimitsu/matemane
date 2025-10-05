class DashboardPage {
    constructor() {
        this.state = {
            inventory: [],
            materialsCount: null,
            groups: [],
            movements: [],
            alerts: [],
            forecasts: [],
            pendingPO: [],
            lastInventoryRefresh: null,
        };

        this.elements = {
            totalInventory: document.getElementById("total-inventory"),
            groupCount: document.getElementById("group-count"),
            materialTypes: document.getElementById("material-types"),
            lastInventoryRefresh: document.getElementById("last-inventory-refresh"),
            pendingPOCount: document.getElementById("pending-po-count"),
            pendingPOWeight: document.getElementById("pending-po-weight"),
            forecastRiskCount: document.getElementById("forecast-risk-count"),
            nearestStockout: document.getElementById("nearest-stockout"),
            groupSnapshot: document.getElementById("groupSnapshot"),
            pendingPOList: document.getElementById("pendingPOList"),
            stockAlerts: document.getElementById("stock-alerts"),
            recentActivities: document.getElementById("recent-activities"),
            stockoutForecast: document.getElementById("stockout-forecast"),
            refreshBtn: document.getElementById("refreshDashboard"),
            refreshStatus: document.getElementById("refresh-status"),
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAll();
    }

    bindEvents() {
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener("click", () => this.loadAll());
        }
    }

    async loadAll() {
        this.setRefreshState(true);
        try {
            const [inventoryGroups, materialsCount, inventoryItems, recentMovements, stockAlerts, forecasts, pendingPOItems] = await Promise.all([
                APIClient.getInventoryGroups({ include_inactive_groups: false }),
                APIClient.getMaterialsCount({ is_active: true }),
                APIClient.getInventory({ limit: 20, has_stock: true, include_zero_stock: false }),
                APIClient.getMovements({ limit: 10 }),
                APIClient.getLowStockItems(5),
                APIClient.getStockoutForecast(),
                APIClient.getPendingPurchaseItems(false),
            ]);

            this.state.groups = inventoryGroups;
            this.state.materialsCount = materialsCount?.total ?? null;
            this.state.inventory = inventoryItems ?? [];
            this.state.movements = recentMovements ?? [];
            this.state.alerts = stockAlerts?.items ?? [];
            this.state.forecasts = forecasts ?? [];
            this.state.pendingPO = pendingPOItems ?? [];
            this.state.lastInventoryRefresh = new Date();

            this.render();
        } catch (error) {
            console.error("Dashboard load error", error);
            Utils.showToast(error.message || "ダッシュボードの更新に失敗しました", "error");
        } finally {
            this.setRefreshState(false);
        }
    }

    setRefreshState(loading) {
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.disabled = loading;
            this.elements.refreshBtn.classList.toggle("opacity-50", loading);
            this.elements.refreshBtn.classList.toggle("cursor-not-allowed", loading);
        }
        if (this.elements.refreshStatus) {
            this.elements.refreshStatus.textContent = loading ? "更新中..." : "更新済み";
        }
    }

    render() {
        this.renderInventorySummary();
        this.renderGroupSnapshot();
        this.renderPendingPO();
        this.renderStockAlerts();
        this.renderRecentMovements();
        this.renderForecasts();
    }

    renderInventorySummary() {
        const totalQuantity = this.state.groups.reduce((sum, group) => sum + (group.total_stock || 0), 0);
        const activeGroupCount = this.state.groups.length;
        const materialCount = typeof this.state.materialsCount === "number" ? this.state.materialsCount : null;

        if (this.elements.totalInventory) {
            this.elements.totalInventory.textContent = Utils.formatNumber(totalQuantity);
        }
        if (this.elements.groupCount) {
            this.elements.groupCount.textContent = `${Utils.formatNumber(activeGroupCount)} グループ`;
        }
        if (this.elements.materialTypes) {
            this.elements.materialTypes.textContent = materialCount != null ? Utils.formatNumber(materialCount) : "-";
        }
        if (this.elements.lastInventoryRefresh) {
            if (this.state.lastInventoryRefresh) {
                this.elements.lastInventoryRefresh.textContent = this.state.lastInventoryRefresh.toLocaleString("ja-JP", {
                    hour: "2-digit",
                    minute: "2-digit",
                });
            } else {
                this.elements.lastInventoryRefresh.textContent = "-";
            }
        }
    }

    renderGroupSnapshot() {
        if (!this.elements.groupSnapshot) return;

        if (!this.state.groups.length) {
            this.elements.groupSnapshot.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-box-open text-3xl mb-3"></i>
                    <p class="text-sm">在庫グループが見つかりませんでした</p>
                </div>
            `;
            return;
        }

        const topGroups = [...this.state.groups]
            .filter(group => (group.total_stock || 0) > 0)
            .sort((a, b) => (b.total_stock || 0) - (a.total_stock || 0))
            .slice(0, 5);

        this.elements.groupSnapshot.innerHTML = topGroups.map(group => `
            <div class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-semibold text-gray-900">${group.group_name}</p>
                        <p class="text-xs text-gray-500 mt-1">材料数: ${group.materials.length} / ロット: ${group.lot_count}</p>
                    </div>
                    <div class="text-right">
                        <div class="text-lg font-bold text-indigo-600">${Utils.formatNumber(group.total_stock)} 本</div>
                        <div class="text-xs text-gray-500">${group.materials.map(m => m.name).join(", ")}</div>
                    </div>
                </div>
            </div>
        `).join("");
    }

    renderPendingPO() {
        if (!this.elements.pendingPOList) return;

        if (!this.state.pendingPO.length) {
            this.elements.pendingPOList.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-clipboard-check text-3xl mb-3"></i>
                    <p class="text-sm">入庫待ち・検品待ちはありません</p>
                </div>
            `;
            this.updatePendingPOSummary();
            return;
        }

        const totalWeight = this.state.pendingPO.reduce((sum, item) => sum + (item.ordered_weight_kg || 0), 0);
        this.updatePendingPOSummary(this.state.pendingPO.length, totalWeight);

        const topPending = this.state.pendingPO.slice(0, 5);
        this.elements.pendingPOList.innerHTML = topPending.map(item => `
            <div class="border border-gray-200 rounded-lg p-4 hover:bg-amber-50 transition">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-semibold text-gray-900">${item.item_name}</p>
                        <p class="text-xs text-gray-500 mt-1">発注番号: ${item.purchase_order?.order_number ?? "-"}</p>
                    </div>
                    <div class="text-right text-sm text-gray-600">
                        <div>${item.ordered_quantity ? `${Utils.formatNumber(item.ordered_quantity)} 本` : "-"}</div>
                        <div>${item.ordered_weight_kg ? `${Utils.formatNumber(item.ordered_weight_kg, 1)} kg` : "-"}</div>
                    </div>
                </div>
            </div>
        `).join("");
    }

    updatePendingPOSummary(count = 0, weight = 0) {
        if (this.elements.pendingPOCount) {
            this.elements.pendingPOCount.textContent = Utils.formatNumber(count) || "-";
        }
        if (this.elements.pendingPOWeight) {
            this.elements.pendingPOWeight.textContent = weight ? `${Utils.formatNumber(weight, 1)} kg` : "- kg";
        }
    }

    renderStockAlerts() {
        if (!this.elements.stockAlerts) return;

        if (!this.state.alerts.length) {
            this.elements.stockAlerts.innerHTML = `
                <div class="text-center py-8">
                    <div class="inline-flex items-center justify-center w-12 h-12 bg-green-50 rounded-full mb-4">
                        <i class="fas fa-check-circle text-2xl text-green-600"></i>
                    </div>
                    <p class="text-gray-700 font-medium">現在アラートはありません</p>
                    <p class="text-sm text-gray-500 mt-1">在庫状況は正常です</p>
                </div>
            `;
            return;
        }

        this.elements.stockAlerts.innerHTML = this.state.alerts.slice(0, 6).map(alert => {
            const levelClass = alert.alert_level === "危険"
                ? "border-red-200 bg-red-50"
                : alert.alert_level === "注意"
                    ? "border-yellow-200 bg-yellow-50"
                    : "border-orange-200 bg-orange-50";
            const iconClass = alert.alert_level === "危険"
                ? "fa-times-circle text-red-600"
                : "fa-exclamation-triangle text-yellow-600";

            return `
                <div class="p-4 border ${levelClass} rounded-xl shadow-sm">
                    <div class="flex items-center">
                        <div class="p-2 bg-white rounded-lg mr-3">
                            <i class="fas ${iconClass}"></i>
                        </div>
                        <div>
                            <p class="text-sm font-semibold">${alert.material_name}</p>
                            <p class="text-xs text-gray-600 mt-1">ロット: ${alert.lot_number} / ${alert.location_name}</p>
                        </div>
                        <div class="ml-auto text-sm font-bold ${alert.alert_level === "危険" ? "text-red-700" : "text-yellow-700"}">
                            ${alert.current_quantity} 本
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    renderRecentMovements() {
        if (!this.elements.recentActivities) return;

        if (!this.state.movements.length) {
            this.elements.recentActivities.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-16 h-16 bg-gray-50 rounded-full mb-4">
                        <i class="fas fa-clock text-2xl text-gray-400"></i>
                    </div>
                    <p class="text-gray-600 font-medium">最近の入出庫はありません</p>
                </div>
            `;
            return;
        }

        this.elements.recentActivities.innerHTML = this.state.movements.map((movement, index) => {
            const isIn = movement.movement_type === "in";
            const badgeClass = isIn ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700";
            const icon = isIn ? "fa-arrow-down" : "fa-arrow-up";

            return `
                <div class="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-all duration-200" style="animation-delay: ${index * 0.05}s">
                    <div class="p-2 ${badgeClass} rounded-lg mr-3">
                        <i class="fas ${icon}"></i>
                    </div>
                    <div class="flex-1">
                        <p class="text-sm font-semibold text-gray-900">${movement.material_name} ${isIn ? "入庫" : "出庫"}</p>
                        <p class="text-xs text-gray-500">
                            ロット ${movement.lot_number} / ${movement.item_management_code}
                        </p>
                    </div>
                    <div class="text-right text-sm text-gray-600">
                        <div>${Utils.formatNumber(movement.quantity)} 本</div>
                        <div>${movement.weight_kg !== undefined ? `${Utils.formatNumber(movement.weight_kg, 3)} kg` : "-"}</div>
                    </div>
                </div>
            `;
        }).join("");
    }

    renderForecasts() {
        if (!this.elements.stockoutForecast) return;

        if (!this.state.forecasts.length) {
            this.elements.stockoutForecast.innerHTML = `
                <div class="text-center py-10 text-gray-500">
                    <i class="fas fa-clipboard-check text-3xl mb-3"></i>
                    <p class="text-sm">在庫切れ予測はありません</p>
                </div>
            `;
            this.updateForecastSummary();
            return;
        }

        const sorted = [...this.state.forecasts]
            .filter(f => f.projected_stockout_date)
            .sort((a, b) => (a.days_until_stockout ?? 9999) - (b.days_until_stockout ?? 9999));

        const top = sorted.slice(0, 5);
        this.updateForecastSummary(top.length, top[0]?.projected_stockout_date);

        this.elements.stockoutForecast.innerHTML = top.map(forecast => `
            <div class="border border-purple-200 bg-purple-50 rounded-lg p-4">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-semibold text-purple-900">${forecast.material_spec}</p>
                        <p class="text-xs text-purple-700 mt-1">現庫: ${Utils.formatNumber(forecast.current_stock_bars)} 本</p>
                    </div>
                    <div class="text-right">
                        <div class="text-sm font-bold text-purple-900">${forecast.projected_stockout_date ?? "-"}</div>
                        <div class="text-xs text-purple-700">${forecast.days_until_stockout != null ? `残り ${forecast.days_until_stockout} 日` : "未計算"}</div>
                    </div>
                </div>
            </div>
        `).join("");
    }

    updateForecastSummary(count = 0, nearestDate = null) {
        if (this.elements.forecastRiskCount) {
            this.elements.forecastRiskCount.textContent = Utils.formatNumber(count) || "-";
        }
        if (this.elements.nearestStockout) {
            this.elements.nearestStockout.textContent = nearestDate ?? "-";
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (window.APIClient && window.Utils) {
        window.dashboardPage = new DashboardPage();
    } else {
        console.error("DashboardPage: 必要な依存関係が読み込まれていません");
    }
});
