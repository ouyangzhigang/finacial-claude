#!/usr/bin/env python
"""Fundamentals analyst: batch financial health check + valuation + red flags."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Raw financial data from eastmoney (Q1 2026) ──
FIN_DATA = {
    '300444': {'name': '双杰电气', 'roe': 14.34, 'profitGrowth': 29615.0, 'deductedGrowth': -62.56, 'grossMargin': 14.77, 'netMargin': 50.58, 'cfRatio': -0.33, 'debtRatio': 73.11, 'currentRatio': 1.17, 'netProfit': 281483071, 'deductedProfit': -49870858, 'bps': 2.63, 'roic': 6.65},
    '601179': {'name': '中国西电', 'roe': 1.50, 'profitGrowth': 17.54, 'deductedGrowth': 6.46, 'grossMargin': 23.35, 'netMargin': 8.06, 'cfRatio': -0.10, 'debtRatio': 45.05, 'currentRatio': 1.73, 'netProfit': 346600770, 'deductedProfit': 370280800, 'bps': 4.56, 'roic': 1.48},
    '002539': {'name': '云图控股', 'roe': 3.18, 'profitGrowth': 19.62, 'deductedGrowth': 0.76, 'grossMargin': 12.28, 'netMargin': 5.11, 'cfRatio': -0.08, 'debtRatio': 64.52, 'currentRatio': 1.08, 'netProfit': 303557057, 'deductedProfit': 255801493, 'bps': 8.04, 'roic': 1.61},
    '603727': {'name': '博迈科', 'roe': -1.85, 'profitGrowth': -608.11, 'deductedGrowth': -157.75, 'grossMargin': 2.04, 'netMargin': -22.86, 'cfRatio': 0.21, 'debtRatio': 29.23, 'currentRatio': 2.50, 'netProfit': -58896204, 'deductedProfit': -61221667, 'bps': 11.15, 'roic': -1.79},
    '300265': {'name': '通光线缆', 'roe': 0.17, 'profitGrowth': -28.15, 'deductedGrowth': 0.29, 'grossMargin': 13.91, 'netMargin': 1.05, 'cfRatio': -0.21, 'debtRatio': 30.26, 'currentRatio': 2.14, 'netProfit': 4012825, 'deductedProfit': 4322771, 'bps': 5.03, 'roic': 0.25},
    '002498': {'name': '汉缆股份', 'roe': 1.81, 'profitGrowth': 12.17, 'deductedGrowth': 2.26, 'grossMargin': 14.66, 'netMargin': 6.24, 'cfRatio': -0.50, 'debtRatio': 33.39, 'currentRatio': 2.34, 'netProfit': 160387370, 'deductedProfit': 136236940, 'bps': 2.65, 'roic': 1.47},
    '603191': {'name': '望变电气', 'roe': 0.49, 'profitGrowth': -15.24, 'deductedGrowth': -10.24, 'grossMargin': 10.14, 'netMargin': 1.33, 'cfRatio': -0.23, 'debtRatio': 64.59, 'currentRatio': 1.64, 'netProfit': 12286841, 'deductedProfit': 4002223, 'bps': 7.59, 'roic': 0.40},
    '002560': {'name': '通达股份', 'roe': 1.06, 'profitGrowth': 81.05, 'deductedGrowth': 8.81, 'grossMargin': 8.28, 'netMargin': 1.99, 'cfRatio': -0.18, 'debtRatio': 51.43, 'currentRatio': 1.75, 'netProfit': 28907574, 'deductedProfit': 28917467, 'bps': 5.23, 'roic': 0.97},
    '603876': {'name': '鼎胜新材', 'roe': 2.55, 'profitGrowth': 127.28, 'deductedGrowth': 23.82, 'grossMargin': 11.13, 'netMargin': 2.64, 'cfRatio': -0.01, 'debtRatio': 70.23, 'currentRatio': 1.08, 'netProfit': 193812231, 'deductedProfit': 193698967, 'bps': 8.22, 'roic': 1.49},
    '603399': {'name': '永杉锂业', 'roe': 8.53, 'profitGrowth': 549.24, 'deductedGrowth': 94.57, 'grossMargin': 16.86, 'netMargin': 6.99, 'cfRatio': -0.18, 'debtRatio': 54.06, 'currentRatio': 1.58, 'netProfit': 132522784, 'deductedProfit': 225544933, 'bps': 3.16, 'roic': 6.01},
    '002240': {'name': '盛新锂能', 'roe': 4.43, 'profitGrowth': 399.89, 'deductedGrowth': 101.33, 'grossMargin': 34.07, 'netMargin': 16.09, 'cfRatio': -0.20, 'debtRatio': 51.49, 'currentRatio': 0.99, 'netProfit': 464035684, 'deductedProfit': 622318509, 'bps': 11.73, 'roic': 2.79},
    '600550': {'name': '保变电气', 'roe': 6.87, 'profitGrowth': 110.39, 'deductedGrowth': 23.15, 'grossMargin': 12.24, 'netMargin': 4.08, 'cfRatio': -0.18, 'debtRatio': 87.48, 'currentRatio': 1.08, 'netProfit': 59563649, 'deductedProfit': 54550172, 'bps': 0.48, 'roic': 2.36},
    '002112': {'name': '三变科技', 'roe': 2.46, 'profitGrowth': 12.28, 'deductedGrowth': 31.23, 'grossMargin': 21.27, 'netMargin': 4.10, 'cfRatio': -0.08, 'debtRatio': 65.51, 'currentRatio': 1.42, 'netProfit': 21068085, 'deductedProfit': 20773837, 'bps': 2.94, 'roic': 1.64},
    '600409': {'name': '三友化工', 'roe': -0.66, 'profitGrowth': -381.27, 'deductedGrowth': -1369.36, 'grossMargin': 9.45, 'netMargin': -2.44, 'cfRatio': -0.10, 'debtRatio': 43.47, 'currentRatio': 1.06, 'netProfit': -91520318, 'deductedProfit': -98004915, 'bps': 6.67, 'roic': -0.37},
    '000155': {'name': '川能动力', 'roe': 2.52, 'profitGrowth': 12.65, 'deductedGrowth': 11.15, 'grossMargin': 61.13, 'netMargin': 37.92, 'cfRatio': -0.26, 'debtRatio': 51.63, 'currentRatio': 3.37, 'netProfit': 266791954, 'deductedProfit': 286644070, 'bps': 5.82, 'roic': 1.99},
    '601678': {'name': '滨化股份', 'roe': 1.26, 'profitGrowth': 52.55, 'deductedGrowth': 47.89, 'grossMargin': 12.81, 'netMargin': 3.93, 'cfRatio': 0.05, 'debtRatio': 49.46, 'currentRatio': 0.75, 'netProfit': 146443573, 'deductedProfit': 119408939, 'bps': 5.68, 'roic': 1.01},
    '601606': {'name': '长城军工', 'roe': -2.52, 'profitGrowth': -2.62, 'deductedGrowth': 8.37, 'grossMargin': 15.28, 'netMargin': -35.55, 'cfRatio': -0.37, 'debtRatio': 49.16, 'currentRatio': 1.59, 'netProfit': -55673796, 'deductedProfit': -60704258, 'bps': 3.01, 'roic': -1.97},
    '000603': {'name': '盛达资源', 'roe': 2.58, 'profitGrowth': 858.53, 'deductedGrowth': 13.01, 'grossMargin': 61.42, 'netMargin': 29.97, 'cfRatio': 0.15, 'debtRatio': 47.33, 'currentRatio': 0.67, 'netProfit': 79405422, 'deductedProfit': 77540889, 'bps': 5.18, 'roic': 2.16},
    '002379': {'name': '宏桥控股', 'roe': 13.81, 'profitGrowth': 37.56, 'deductedGrowth': 1857.14, 'grossMargin': 24.03, 'netMargin': 16.51, 'cfRatio': 0.23, 'debtRatio': 52.36, 'currentRatio': 1.41, 'netProfit': 6757771303, 'deductedProfit': 6795854852, 'bps': 4.01, 'roic': 9.44},
    '600219': {'name': '南山铝业', 'roe': 2.09, 'profitGrowth': -35.39, 'deductedGrowth': -13.31, 'grossMargin': 21.64, 'netMargin': 13.51, 'cfRatio': 0.12, 'debtRatio': 18.44, 'currentRatio': 3.18, 'netProfit': 1100775007, 'deductedProfit': 1082014179, 'bps': 4.44, 'roic': 1.83},
    '300191': {'name': '潜能恒信', 'roe': 2.68, 'profitGrowth': 539.12, 'deductedGrowth': 59.34, 'grossMargin': 44.52, 'netMargin': 14.41, 'cfRatio': 0.46, 'debtRatio': 71.95, 'currentRatio': 0.50, 'netProfit': 30497716, 'deductedProfit': 30472546, 'bps': 3.61, 'roic': 1.67},
    '000862': {'name': '银星能源', 'roe': 1.29, 'profitGrowth': -23.55, 'deductedGrowth': -48.07, 'grossMargin': 35.92, 'netMargin': 18.74, 'cfRatio': 0.04, 'debtRatio': 49.21, 'currentRatio': 0.75, 'netProfit': 55478131, 'deductedProfit': 55008219, 'bps': 4.73, 'roic': 1.56},
    '002546': {'name': '新联电子', 'roe': 2.37, 'profitGrowth': -15.04, 'deductedGrowth': 0.10, 'grossMargin': 40.94, 'netMargin': 46.42, 'cfRatio': 0.08, 'debtRatio': 8.49, 'currentRatio': 12.74, 'netProfit': 91152717, 'deductedProfit': 40355903, 'bps': 4.66, 'roic': 2.35},
    '600468': {'name': '百利电气', 'roe': 1.26, 'profitGrowth': -20.15, 'deductedGrowth': -10.61, 'grossMargin': 19.86, 'netMargin': 5.06, 'cfRatio': -0.32, 'debtRatio': 44.31, 'currentRatio': 1.66, 'netProfit': 25531409, 'deductedProfit': 22490540, 'bps': 1.87, 'roic': 1.30},
    '600089': {'name': '特变电工', 'roe': 2.55, 'profitGrowth': 13.40, 'deductedGrowth': -1.26, 'grossMargin': 21.12, 'netMargin': 8.58, 'cfRatio': 0.02, 'debtRatio': 56.58, 'currentRatio': 1.21, 'netProfit': 1814529515, 'deductedProfit': 1460823600, 'bps': 14.24, 'roic': 1.58},
    '600698': {'name': '湖南天雁', 'roe': 0.25, 'profitGrowth': 109.54, 'deductedGrowth': 3.91, 'grossMargin': 11.23, 'netMargin': 1.14, 'cfRatio': -0.10, 'debtRatio': 39.78, 'currentRatio': 1.53, 'netProfit': 1849446, 'deductedProfit': 205333, 'bps': 0.69, 'roic': 0.25},
    '002829': {'name': '星网宇达', 'roe': -1.70, 'profitGrowth': -125.86, 'deductedGrowth': -3.04, 'grossMargin': 21.90, 'netMargin': -53.83, 'cfRatio': -1.17, 'debtRatio': 25.71, 'currentRatio': 2.84, 'netProfit': -26534158, 'deductedProfit': -18283681, 'bps': 7.45, 'roic': -1.56},
    '600354': {'name': '敦煌种业', 'roe': 6.52, 'profitGrowth': -26.03, 'deductedGrowth': -70.02, 'grossMargin': 43.96, 'netMargin': 24.92, 'cfRatio': 0.05, 'debtRatio': 50.00, 'currentRatio': 1.81, 'netProfit': 47249790, 'deductedProfit': 46220758, 'bps': 1.42, 'roic': 13.88},
    '600173': {'name': '卧龙新能', 'roe': 0.33, 'profitGrowth': -65.97, 'deductedGrowth': -16.06, 'grossMargin': 20.80, 'netMargin': 5.87, 'cfRatio': 0.84, 'debtRatio': 47.89, 'currentRatio': 1.66, 'netProfit': 11922930, 'deductedProfit': 9873166, 'bps': 5.10, 'roic': 0.57},
    '002490': {'name': '山东墨龙', 'roe': 1.11, 'profitGrowth': 2.96, 'deductedGrowth': 30.35, 'grossMargin': 10.25, 'netMargin': 0.84, 'cfRatio': 0.14, 'debtRatio': 81.97, 'currentRatio': 0.83, 'netProfit': 5583952, 'deductedProfit': 3470015, 'bps': 0.63, 'roic': 1.70},
    '002300': {'name': '太阳电缆', 'roe': 0.85, 'profitGrowth': -23.11, 'deductedGrowth': 3.76, 'grossMargin': 2.77, 'netMargin': 0.25, 'cfRatio': -0.05, 'debtRatio': 65.10, 'currentRatio': 1.15, 'netProfit': 16106115, 'deductedProfit': 14439136, 'bps': 2.64, 'roic': 0.33},
    '002606': {'name': '大连电瓷', 'roe': 3.07, 'profitGrowth': 194.21, 'deductedGrowth': 20.28, 'grossMargin': 37.55, 'netMargin': 14.18, 'cfRatio': 0.08, 'debtRatio': 36.96, 'currentRatio': 2.00, 'netProfit': 59504934, 'deductedProfit': 55401140, 'bps': 4.49, 'roic': 2.56},
    '001208': {'name': '华菱线缆', 'roe': 1.04, 'profitGrowth': -5.34, 'deductedGrowth': -6.73, 'grossMargin': 10.36, 'netMargin': 2.68, 'cfRatio': -0.08, 'debtRatio': 56.83, 'currentRatio': 1.30, 'netProfit': 30444253, 'deductedProfit': 21983174, 'bps': 4.61, 'roic': 0.96},
    '002339': {'name': '积成电子', 'roe': -4.12, 'profitGrowth': -19.59, 'deductedGrowth': -147.58, 'grossMargin': 16.25, 'netMargin': -16.39, 'cfRatio': -0.37, 'debtRatio': 49.31, 'currentRatio': 1.89, 'netProfit': -73379824, 'deductedProfit': -79409227, 'bps': 3.46, 'roic': -2.55},
    '002358': {'name': '森源电气', 'roe': 1.60, 'profitGrowth': 26.27, 'deductedGrowth': 23.24, 'grossMargin': 27.56, 'netMargin': 6.93, 'cfRatio': -0.15, 'debtRatio': 52.49, 'currentRatio': 1.44, 'netProfit': 53202093, 'deductedProfit': 55845423, 'bps': 3.61, 'roic': 1.28},
    '002218': {'name': '拓日新能', 'roe': -1.02, 'profitGrowth': 1.25, 'deductedGrowth': 1.21, 'grossMargin': 10.42, 'netMargin': -17.46, 'cfRatio': 0.12, 'debtRatio': 38.69, 'currentRatio': 2.37, 'netProfit': -40303051, 'deductedProfit': -42284302, 'bps': 2.79, 'roic': -0.48},
    '600990': {'name': '四创电子', 'roe': -3.64, 'profitGrowth': -171.32, 'deductedGrowth': -12.03, 'grossMargin': 17.15, 'netMargin': -33.67, 'cfRatio': -1.29, 'debtRatio': 71.31, 'currentRatio': 1.14, 'netProfit': -57329041, 'deductedProfit': -59237804, 'bps': 5.71, 'roic': -1.37},
    '000035': {'name': '中国天楹', 'roe': 1.02, 'profitGrowth': 5.25, 'deductedGrowth': 10.48, 'grossMargin': 36.59, 'netMargin': 10.42, 'cfRatio': 0.26, 'debtRatio': 66.13, 'currentRatio': 0.68, 'netProfit': 110716961, 'deductedProfit': 125036004, 'bps': 4.51, 'roic': 1.01},
    '600513': {'name': '联环药业', 'roe': 0.50, 'profitGrowth': -72.14, 'deductedGrowth': -50.49, 'grossMargin': 26.52, 'netMargin': 0.91, 'cfRatio': -0.10, 'debtRatio': 59.39, 'currentRatio': 0.94, 'netProfit': 6424752, 'deductedProfit': 5611568, 'bps': 4.48, 'roic': 0.48},
    '600449': {'name': '宁夏建材', 'roe': -0.06, 'profitGrowth': 46.17, 'deductedGrowth': 5.03, 'grossMargin': 6.99, 'netMargin': -1.36, 'cfRatio': -0.21, 'debtRatio': 17.16, 'currentRatio': 3.23, 'netProfit': -4525905, 'deductedProfit': -11595395, 'bps': 15.41, 'roic': -0.21},
    '603050': {'name': '科林电气', 'roe': 2.23, 'profitGrowth': -41.70, 'deductedGrowth': -13.56, 'grossMargin': 18.62, 'netMargin': 4.89, 'cfRatio': -0.17, 'debtRatio': 60.18, 'currentRatio': 1.37, 'netProfit': 42389948, 'deductedProfit': 34656247, 'bps': 4.76, 'roic': 1.94},
    '603618': {'name': '杭电股份', 'roe': 2.94, 'profitGrowth': 279.96, 'deductedGrowth': 18.77, 'grossMargin': 12.29, 'netMargin': 3.68, 'cfRatio': -0.13, 'debtRatio': 74.30, 'currentRatio': 1.16, 'netProfit': 80841906, 'deductedProfit': 76706086, 'bps': 3.91, 'roic': 1.27},
    '600343': {'name': '航天动力', 'roe': -1.73, 'profitGrowth': 15.05, 'deductedGrowth': 1.86, 'grossMargin': 15.94, 'netMargin': -20.31, 'cfRatio': -0.67, 'debtRatio': 48.90, 'currentRatio': 1.45, 'netProfit': -22233558, 'deductedProfit': -23385862, 'bps': 2.00, 'roic': -1.09},
    '600379': {'name': '宝光股份', 'roe': 1.18, 'profitGrowth': -50.80, 'deductedGrowth': -21.00, 'grossMargin': 20.37, 'netMargin': 5.01, 'cfRatio': -0.23, 'debtRatio': 58.40, 'currentRatio': 1.39, 'netProfit': 9222471, 'deductedProfit': 8482464, 'bps': 2.38, 'roic': 1.65},
}

# PE data from tencent_quote
PE_DATA = {
    '300444': {'pe': 16.47, 'price': 9.54, 'mktcap': 76.76},
    '601179': {'pe': 52.95, 'price': 13.65, 'mktcap': 699.68},
    '002539': {'pe': 15.70, 'price': 11.40, 'mktcap': 137.68},
    '603727': {'pe': -543.51, 'price': 17.44, 'mktcap': 49.13},
    '300265': {'pe': 220.07, 'price': 14.40, 'mktcap': 67.33},
    '002498': {'pe': 34.44, 'price': 5.91, 'mktcap': 196.61},
    '603191': {'pe': 65.96, 'price': 13.40, 'mktcap': 44.22},
    '002560': {'pe': 25.13, 'price': 5.96, 'mktcap': 43.82},
    '603876': {'pe': 31.55, 'price': 21.10, 'mktcap': 196.08},
    '603399': {'pe': -41.02, 'price': 13.72, 'mktcap': 70.29},
    '002240': {'pe': -103.39, 'price': 30.42, 'mktcap': 278.43},
    '600550': {'pe': 93.98, 'price': 11.65, 'mktcap': 214.54},
    '002112': {'pe': 262.98, 'price': 14.52, 'mktcap': 42.71},
    '600409': {'pe': 797.88, 'price': 6.58, 'mktcap': 135.83},
    '000155': {'pe': 42.61, 'price': 12.29, 'mktcap': 226.89},
    '601678': {'pe': 54.34, 'price': 6.22, 'mktcap': 149.84},
    '601606': {'pe': 3047.14, 'price': 29.14, 'mktcap': 211.04},
    '000603': {'pe': 28.38, 'price': 24.83, 'mktcap': 171.32},
    '002379': {'pe': 13.52, 'price': 20.45, 'mktcap': 2664.86},
    '600219': {'pe': 13.31, 'price': 4.79, 'mktcap': 550.07},
    '300191': {'pe': 147.36, 'price': 31.87, 'mktcap': 101.98},
    '000862': {'pe': 198.52, 'price': 5.92, 'mktcap': 54.34},
    '002546': {'pe': 12.20, 'price': 8.22, 'mktcap': 68.56},
    '600468': {'pe': 72.94, 'price': 5.54, 'mktcap': 60.26},
    '600089': {'pe': 17.64, 'price': 21.53, 'mktcap': 1087.87},
    '600698': {'pe': -219.04, 'price': 6.22, 'mktcap': 66.47},
    '002829': {'pe': -35.32, 'price': 21.08, 'mktcap': 43.81},
    '600354': {'pe': 104.11, 'price': 6.04, 'mktcap': 31.88},
    '600173': {'pe': -20.47, 'price': 6.14, 'mktcap': 43.01},
    '002490': {'pe': 1235.11, 'price': 8.23, 'mktcap': 65.66},
    '002300': {'pe': 59.50, 'price': 6.45, 'mktcap': 46.59},
    '002606': {'pe': 23.79, 'price': 13.61, 'mktcap': 59.76},
    '001208': {'pe': 80.09, 'price': 13.61, 'mktcap': 86.88},
    '002339': {'pe': 435.74, 'price': 7.04, 'mktcap': 35.49},
    '002358': {'pe': 51.92, 'price': 5.50, 'mktcap': 51.14},
    '002218': {'pe': -27.10, 'price': 3.82, 'mktcap': 53.80},
    '600990': {'pe': -14.16, 'price': 16.94, 'mktcap': 45.92},
    '000035': {'pe': 39.85, 'price': 4.83, 'mktcap': 115.34},
    '600513': {'pe': -41.14, 'price': 16.57, 'mktcap': 47.30},
    '600449': {'pe': 31.60, 'price': 12.29, 'mktcap': 58.77},
    '603050': {'pe': 33.08, 'price': 18.67, 'mktcap': 75.30},
    '603618': {'pe': -79.05, 'price': 27.34, 'mktcap': 189.02},
    '600343': {'pe': -63.20, 'price': 18.68, 'mktcap': 119.22},
    '600379': {'pe': 91.06, 'price': 11.52, 'mktcap': 38.04},
}


def check_red_flags(code, fin, pe_info):
    """Check hard red flags and soft warnings."""
    flags = []
    pe = pe_info['pe']
    pg = fin['profitGrowth']
    netProfit = fin['netProfit']
    deductedProfit = fin['deductedProfit']
    debtRatio = fin['debtRatio']
    cfRatio = fin['cfRatio']
    currentRatio = fin['currentRatio']

    # ── Hard red flags (一票否决) ──
    # 1. PE > 200 and no growth
    if pe > 200 and pg <= 0:
        flags.append({
            'flag': 'PE>200且无利润增速',
            'severity': 'red',
            'threshold': 'PE>200需利润增速>0',
            'actual': f'PE={pe}, 利润增速={pg}%',
            'action': '剔除'
        })

    # 2. TTM loss-making
    if pe < 0:
        flags.append({
            'flag': 'TTM亏损',
            'severity': 'red',
            'threshold': 'PE>0',
            'actual': f'PE={pe}',
            'action': '剔除'
        })

    # 3. Goodwill > 30% of net assets (data missing from available sources, skip)

    # ── Soft warnings (降权) ──
    # Debt ratio > 80%
    if debtRatio > 80:
        flags.append({
            'flag': '资产负债率过高',
            'severity': 'yellow',
            'threshold': '<80%',
            'actual': f'{debtRatio}%',
            'action': '降权'
        })

    # Cash flow / revenue < 0
    if cfRatio < 0:
        flags.append({
            'flag': '经营现金流/营收为负',
            'severity': 'yellow',
            'threshold': '>0',
            'actual': f'{cfRatio:.2f}',
            'action': '降权'
        })

    # Non-recurring profit ratio > 20%
    if netProfit > 0 and deductedProfit < netProfit * 0.8:
        nonRecurRatio = (netProfit - deductedProfit) / netProfit * 100
        if nonRecurRatio > 20:
            flags.append({
                'flag': '非经常性损益占比过高',
                'severity': 'yellow',
                'threshold': '<20%',
                'actual': f'{nonRecurRatio:.0f}%',
                'action': '降权'
            })

    # Current ratio < 1
    if currentRatio < 1:
        flags.append({
            'flag': '流动比率<1',
            'severity': 'yellow',
            'threshold': '>1',
            'actual': f'{currentRatio:.2f}',
            'action': '降权'
        })

    # PE > 200 with positive growth (borderline)
    if pe > 200 and pg > 0:
        flags.append({
            'flag': 'PE畸高但仍有增速',
            'severity': 'yellow',
            'threshold': 'PE<200或增速>30%',
            'actual': f'PE={pe}, 增速={pg}%',
            'action': '降权'
        })

    # PE 100-200 with negative growth
    if 100 <= pe <= 200 and pg < 0:
        flags.append({
            'flag': 'PE偏高且利润负增长',
            'severity': 'yellow',
            'threshold': 'PE<100或增速>0',
            'actual': f'PE={pe}, 增速={pg}%',
            'action': '降权'
        })

    return flags


def fin_verdict(roe):
    if roe >= 10:
        return '优秀'
    elif roe >= 5:
        return '良好'
    elif roe >= 2:
        return '一般'
    elif roe >= 0:
        return '偏低'
    else:
        return '亏损'


def val_verdict(pe):
    if pe < 0:
        return '亏损无法估值'
    elif pe <= 20:
        return '低估'
    elif pe <= 40:
        return '合理'
    elif pe <= 80:
        return '偏高'
    elif pe <= 200:
        return '高估'
    else:
        return '严重高估'


def main():
    results = {}
    for code in FIN_DATA:
        fin = FIN_DATA[code]
        pe_info = PE_DATA[code]
        flags = check_red_flags(code, fin, pe_info)

        hasRed = any(f['severity'] == 'red' for f in flags)
        hasYellow = any(f['severity'] == 'yellow' for f in flags)

        if hasRed:
            verdict = '剔除'
        elif hasYellow:
            verdict = '降权'
        else:
            verdict = '通过'

        # Calculate PB
        bps = fin['bps']
        price = pe_info['price']
        pb = round(price / bps, 2) if bps and bps > 0 else None

        # Non-recurring profit ratio
        nonRecurRatio = None
        if fin['netProfit'] > 0:
            nonRecurRatio = round((fin['netProfit'] - fin['deductedProfit']) / fin['netProfit'] * 100, 1)

        results[code] = {
            'name': fin['name'],
            'financials': {
                'roe': fin['roe'],
                'roeTrend': '数据缺失(单季)',
                'cashflowRatio': round(fin['cfRatio'], 2),
                'netProfitGrowth': fin['profitGrowth'],
                'deductedGrowth': fin['deductedGrowth'],
                'grossMargin': fin['grossMargin'],
                'netMargin': fin['netMargin'],
                'debtRatio': fin['debtRatio'],
                'currentRatio': fin['currentRatio'],
                'roic': fin['roic'],
                'nonRecurRatio': nonRecurRatio,
                'verdict': fin_verdict(fin['roe'])
            },
            'valuation': {
                'peTtm': pe_info['pe'],
                'pb': pb,
                'price': price,
                'mktcap': pe_info['mktcap'],
                'pePercentile5y': '数据缺失',
                'pbPercentile5y': '数据缺失',
                'relativeToPeers': '数据缺失',
                'verdict': val_verdict(pe_info['pe'])
            },
            'redFlags': flags,
            'verdict': verdict,
            'summary': ''
        }

        # Generate summary
        name = fin['name']
        if hasRed:
            redReasons = [f['flag'] for f in flags if f['severity'] == 'red']
            results[code]['summary'] = f'{name}: 硬雷点({"、".join(redReasons)})，一票否决'
        elif hasYellow:
            yellowReasons = [f['flag'] for f in flags if f['severity'] == 'yellow']
            results[code]['summary'] = f'{name}: PE={pe_info["pe"]}, ROE={fin["roe"]}%, 负债率={fin["debtRatio"]}%, 软警示({"、".join(yellowReasons)})，降权'
        else:
            results[code]['summary'] = f'{name}: PE={pe_info["pe"]}, ROE={fin["roe"]}%, 负债率={fin["debtRatio"]}%, 财务健康，通过'

    # Count verdicts
    passCount = sum(1 for r in results.values() if r['verdict'] == '通过')
    warnCount = sum(1 for r in results.values() if r['verdict'] == '降权')
    rejectCount = sum(1 for r in results.values() if r['verdict'] == '剔除')

    output = {
        'agent': 'fundamentals-analyst',
        'asOf': '20260723',
        'data': {
            'summary': f'通过: {passCount}, 降权: {warnCount}, 剔除: {rejectCount}',
            'passCount': passCount,
            'warnCount': warnCount,
            'rejectCount': rejectCount,
            'rejectReason': {
                'PE>200且无增速': [c for c, r in results.items() if any(f['flag'] == 'PE>200且无利润增速' and f['severity'] == 'red' for f in r['redFlags'])],
                'TTM亏损': [c for c, r in results.items() if any(f['flag'] == 'TTM亏损' and f['severity'] == 'red' for f in r['redFlags'])],
            },
            'dataSource': '腾讯qt.gtimg.cn(PE/PB/市值) + 东方财富datacenter(财务指标Q1 2026)',
            'dataQuality': 'MCP全SSL挂未使用; 商誉数据缺失(东财资产负债表接口无商誉字段); PE/PB分位数据缺失; 财务数据为2026Q1单季同比',
            'stocks': results
        },
        'keyFields': {
            'passCodes': ','.join(c for c, r in results.items() if r['verdict'] == '通过'),
            'warnCodes': ','.join(c for c, r in results.items() if r['verdict'] == '降权'),
            'rejectCodes': ','.join(c for c, r in results.items() if r['verdict'] == '剔除'),
            'passCount': passCount,
            'rejectCount': rejectCount,
            'hardRedFlags': ['PE>200且无增速', 'TTM亏损', '商誉>30%(数据缺失)'],
            'dataSource': '腾讯qt.gtimg.cn + 东方财富datacenter Q1 2026'
        }
    }

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'data', 'runs', '20260723_short-term-picks', 'fundamentals-analyst.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'Written to {out_path}')
    print(f'通过: {passCount}, 降权: {warnCount}, 剔除: {rejectCount}')
    print()
    print('=== 剔除 ===')
    for c, r in results.items():
        if r['verdict'] == '剔除':
            print(f'{c} {r["name"]}: {r["summary"]}')
    print()
    print('=== 降权 ===')
    for c, r in results.items():
        if r['verdict'] == '降权':
            print(f'{c} {r["name"]}: {r["summary"]}')
    print()
    print('=== 通过 ===')
    for c, r in results.items():
        if r['verdict'] == '通过':
            print(f'{c} {r["name"]}: {r["summary"]}')


if __name__ == '__main__':
    main()