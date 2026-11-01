import { jsPDF } from "jspdf";
import { api } from "@/lib/api";

const load = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });

const toImg = async (url) => {
  const { data } = await api.get(url, { responseType: "blob", baseURL: "" });
  const src = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(data); });
  const i = await load(src);
  return { src, w: i.width, h: i.height };
};

const logoImg = async () => {
  const i = await load("/logo-trim.png");
  return { src: i, w: i.width, h: i.height };
};

const fit = (img, bw, bh) => {
  const s = Math.min(bw / img.w, bh / img.h);
  return [img.w * s, img.h * s];
};

// Agency book: black cover with the My Atelier logo, then one A4 landscape page per pose with only PRIMA / DOPO.
export async function exportPosePdf(pages) {
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const W = 297, H = 210, band = 18;
  const logo = await logoImg();
  pdf.setFillColor(0, 0, 0);
  pdf.rect(0, 0, W, H, "F");
  const [lw, lh] = fit(logo, 150, 70);
  pdf.addImage(logo.src, "PNG", (W - lw) / 2, (H - lh) / 2, lw, lh);
  for (const p of pages) {
    const [b, a] = await Promise.all([toImg(p.before), toImg(p.after)]);
    pdf.addPage();
    pdf.setFillColor(0, 0, 0);
    pdf.rect(0, 0, W, band, "F");
    const [sw, sh] = fit(logo, 40, band - 6);
    pdf.addImage(logo.src, "PNG", 12, (band - sh) / 2, sw, sh);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(60, 60, 60);
    const gap = 10, bw = (W - 24 - gap) / 2, top = band + 12, bh = H - top - 8;
    [[b, "PRIMA", 12], [a, "DOPO", 12 + bw + gap]].forEach(([img, label, x]) => {
      const [w, h] = fit(img, bw, bh);
      pdf.text(label, x + bw / 2, band + 8, { align: "center", charSpace: 1.5 });
      pdf.addImage(img.src, "JPEG", x + (bw - w) / 2, top + (bh - h) / 2, w, h);
    });
  }
  pdf.save("my-atelier-book-prima-dopo.pdf");
}
