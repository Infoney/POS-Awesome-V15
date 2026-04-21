/**
 * Utility functions for responsive item card layout.
 */

/**
 * Number of columns in the item card grid.
 *
 * The POS uses Command-Center-style horizontal row cards — a single
 * column at every breakpoint. The classic 2/3-column grid is retained
 * as dead code below in case a future flag re-enables it.
 */
export const getCardColumns = (_width: number): number => 1;

/**
 * Calculates the gap between cards based on container width.
 */
export const getCardGap = (width: number): number => {
    if (width <= 768) {
        return 10;
    }
    if (width <= 1200) {
        return 12;
    }
    return 16;
};

/**
 * Calculates the padding for the card container based on container width.
 */
export const getCardPadding = (width: number): number => {
    if (width <= 768) {
        return 10;
    }
    if (width <= 1200) {
        return 12;
    }
    return 16;
};
