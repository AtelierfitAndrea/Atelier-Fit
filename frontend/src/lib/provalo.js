import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";

// Import the product photo (if any) and open the Studio with the recommended size preset.
export const useProvalo = () => {
  const navigate = useNavigate();
  const [importing, setImporting] = useState(false);
  const provalo = async (result) => {
    if (!result) return;
    setImporting(true);
    try {
      let garment_path = null;
      if (result.product_image_url) {
        const { data } = await api.post("/product/import-image", {
          image_url: result.product_image_url, category: result.category, name: result.product_name,
        });
        garment_path = data.path;
      }
      navigate("/studio", {
        state: {
          preset: {
            garment_path,
            name: [result.brand, result.product_name].filter(Boolean).join(" · "),
            category: (result.category || "top").toLowerCase(),
            chosen_size: result.recommended_size,
          },
        },
      });
    } catch {
      toast.error("Non siamo riusciti a importare la foto del prodotto. Caricala manualmente nello Studio.");
      navigate("/studio");
    } finally {
      setImporting(false);
    }
  };
  return { provalo, importing };
};
