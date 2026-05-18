/** TEFAS Platform — finans terimleri sözlüğü */

export const GLOSSARY: Record<string, string> = {
  Sharpe:
    "Risk başına getiri ölçüsüdür. Fonun fazla getirisinin, üstlendiği oynaklığa (volatilite) oranını gösterir; yüksek Sharpe genelde daha verimli risk-getiri profili anlamına gelir.",
  "Standart Sapma":
    "Fon getirilerinin ortalamadan ne kadar saptığını ölçer; yüksek standart sapma daha oynak (riskli) fiyat hareketleri demektir.",
  "Max Drawdown":
    "Fonun geçmişteki en yüksek değerinden en düşük değerine kadar yaşadığı maksimum tepe-dip kaybı (%). Büyük drawdown uzun toparlanma süreleri anlamına gelebilir.",
  "Net Akış":
    "Belirli bir günde fona giren ve çıkan nakit farkıdır. Pozitif net akış yatırımcı ilgisinin arttığını, negatif akış ise çıkış baskısını gösterir.",
  KYD:
    "Kurucu Yatırım Danışmanlığı — fonun performans, risk ve ücret metriklerinin karşılaştırmalı özetlendiği standart bilgi setidir.",
  "Yönetim Ücreti":
    "Fonun yıllık yönetim komisyon oranıdır (%). Bu platformda resmi veri yoksa kategori bazlı tahmini değer gösterilir.",
  Beta:
    "Fonun bir endekse (ör. BIST) göre duyarlılığını ölçer. Beta > 1 piyasa ortalamasından daha oynak, Beta < 1 daha az oynak hareket eder.",
  Volatilite:
    "Fiyat veya getirilerin dalgalanma derecesidir; genelde günlük getirilerin standart sapması ile hesaplanır.",
  "30 Gün Getiri":
    "Son 30 işlem gününde birim fiyatın yüzde bazda toplam değişimidir.",
  "Risk Seviyesi":
    "Fonun kategori ve varlık yapısına göre düşük, orta veya yüksek risk sınıflandırmasıdır.",
  AUM:
    "Assets Under Management — fonun toplam yönetilen varlık büyüklüğü (piyasa değeri).",
};

export function getGlossaryDefinition(term: string): string | undefined {
  return GLOSSARY[term];
}
