const nf = new Intl.NumberFormat("ar", { maximumFractionDigits: 1 });

export const formatNumber = (n: number): string => nf.format(n);
