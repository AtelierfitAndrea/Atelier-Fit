import { jsPDF } from "jspdf";
import { api } from "@/lib/api";

const toImg = async (url) => {
  const { data } = await api.get(url, { responseType: "blob", baseURL: "" });
  const src = await new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(data); });
  const dim = await new Promise((ok) => { const i = new Image(); i.onload = () => ok([i.width, i.height]); i.src = src; });
  return { src, w: dim[0], h: dim[1] };
};

const fit = (img, bw, bh) => {
  const s = Math.min(bw / img.w, bh / img.h);
  return [img.w * s, img.h * s];
};

// A4 landscape: cover + one page per pose with Before / After side by side.
export async function exportPosePdf(pages) {
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const W = 297, H = 210;
  pdf.setFont("times", "normal");
  pdf.setFontSize(34);
  pdf.text("My Atelier", 20, 80);
  pdf.setFontSize(14);
  pdf.text("Virtual Try-On - Prima / Dopo - pose social", 20, 95);
  pdf.setFontSize(10);
  pdf.text(new Date().toLocaleDateString("it-IT"), 20, 105);
  for (const p of pages) {
    const [b, a] = await Promise.all([toImg(p.before), toImg(p.after)]);
    pdf.addPage();
    pdf.setFontSize(16);
    pdf.text(p.title, 15, 16);
    pdf.setFontSize(9);
    const bw = (W - 45) / 2, bh = H - 45;
    [[b, "PRIMA", 15], [a, "DOPO", 30 + bw]].forEach(([img, label, x]) => {
      const [w, h] = fit(img, bw, bh);
      pdf.text(label, x, 26);
      pdf.addImage(img.src, "JPEG", x + (bw - w) / 2, 30 + (bh - h) / 2, w, h);
    });
    pdf.text("My Atelier - Virtual Try-On", 15, H - 8);
  }
  pdf.save("my-atelier-prima-dopo.pdf");
}
