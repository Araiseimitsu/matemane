// 共通ページネーションユーティリティ

/**
 * ページネーションUIを生成して表示
 * @param {string} prefix - ページネーションの識別子（'orders', 'receiving', 'inspection', 'print', 'inventory', 'materials'）
 * @param {number} currentPage - 現在のページ番号
 * @param {number} totalPages - 総ページ数
 * @param {Function} loadFunc - ページロード関数
 */
function renderPagination(prefix, currentPage, totalPages, loadFunc) {
    const topContainer = document.getElementById(`${prefix}PaginationTop`);
    const bottomContainer = document.getElementById(`${prefix}PaginationBottom`);

    if (!topContainer && !bottomContainer) {
        console.warn(`ページネーションコンテナが見つかりません: ${prefix}`);
        return;
    }

    // ページネーションHTMLを生成
    const paginationHTML = createPaginationHTML(currentPage, totalPages, loadFunc);

    // 上部と下部に同じページネーションを表示
    if (topContainer) {
        topContainer.innerHTML = paginationHTML;
    }
    if (bottomContainer) {
        bottomContainer.innerHTML = paginationHTML;
    }
}

/**
 * ページネーションHTMLを生成
 * @param {number} currentPage - 現在のページ番号
 * @param {number} totalPages - 総ページ数
 * @param {Function} loadFunc - ページロード関数
 * @returns {string} ページネーションHTML
 */
function createPaginationHTML(currentPage, totalPages, loadFunc) {
    if (totalPages <= 1) {
        return '';
    }

    const funcName = loadFunc.name;
    let html = '<div class="flex items-center justify-between bg-white rounded-lg p-3 border border-gray-200">';

    // ページ情報
    html += `<div class="text-sm text-gray-700">
        ページ <span class="font-medium">${currentPage}</span> / <span class="font-medium">${totalPages}</span>
    </div>`;

    // ページネーションボタン
    html += '<div class="flex items-center space-x-2">';

    // 最初へ
    if (currentPage > 1) {
        html += `<button onclick="${funcName}(1)" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-double-left"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-double-left"></i>
        </button>`;
    }

    // 前へ
    if (currentPage > 1) {
        html += `<button onclick="${funcName}(${currentPage - 1})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-left"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-left"></i>
        </button>`;
    }

    // ページ番号ボタン（最大7個表示）
    const pageButtons = getPageNumbers(currentPage, totalPages);
    pageButtons.forEach(pageNum => {
        if (pageNum === '...') {
            html += `<span class="px-2 text-gray-500">...</span>`;
        } else {
            if (pageNum === currentPage) {
                html += `<button class="px-3 py-1 bg-blue-600 text-white rounded font-medium text-sm">${pageNum}</button>`;
            } else {
                html += `<button onclick="${funcName}(${pageNum})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">${pageNum}</button>`;
            }
        }
    });

    // 次へ
    if (currentPage < totalPages) {
        html += `<button onclick="${funcName}(${currentPage + 1})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-right"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-right"></i>
        </button>`;
    }

    // 最後へ
    if (currentPage < totalPages) {
        html += `<button onclick="${funcName}(${totalPages})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-double-right"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-double-right"></i>
        </button>`;
    }

    html += '</div></div>';

    return html;
}

/**
 * 表示するページ番号の配列を取得
 * @param {number} current - 現在のページ
 * @param {number} total - 総ページ数
 * @returns {Array} ページ番号配列（'...'を含む）
 */
function getPageNumbers(current, total) {
    if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    // 現在ページが先頭付近
    if (current <= 4) {
        return [1, 2, 3, 4, 5, '...', total];
    }

    // 現在ページが末尾付近
    if (current >= total - 3) {
        return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
    }

    // 現在ページが中央
    return [1, '...', current - 1, current, current + 1, '...', total];
}
