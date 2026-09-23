import { useState } from "react";

export default function FeedbackModal({ isOpen, onClose, currentBuild, backendUrl }) {
  const [category, setCategory] = useState("Bug");
  const [description, setDescription] = useState("");
  const [contact, setContact] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  if (!isOpen) return null;

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 4 * 1024 * 1024) {
        alert("Image must be smaller than 4MB");
        return;
      }
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("category", category);
      formData.append("description", description);
      formData.append("contact", contact);
      formData.append("build_snapshot", JSON.stringify(currentBuild || {}));
      if (imageFile) {
        formData.append("screenshot", imageFile);
      }

      const res = await fetch(`${backendUrl}/feedback`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Failed to submit feedback");
      setSubmitSuccess(true);
      setTimeout(() => {
        setSubmitSuccess(false);
        onClose();
      }, 2200);
    } catch (err) {
      console.error(err);
      alert("Submission error. Please make sure the backend is reachable.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 w-full max-w-lg rounded-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="font-extrabold text-slate-900 text-base">Send Feedback & Report</h3>
            <p className="text-xs text-slate-500">Share your experience or report an anomaly</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-sm">
            ✕
          </button>
        </div>

        {submitSuccess ? (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-6 rounded-xl text-center space-y-2">
            <span className="text-3xl">✓</span>
            <h4 className="font-bold text-sm">Report Logged!</h4>
            <p className="text-xs">Your notes, hardware snapshot, and screenshot have been securely recorded for the developer.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Feedback Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs font-bold outline-none"
              >
                <option value="Bug">Software Bug / Glitch</option>
                <option value="Hardware Conflict">Incorrect Hardware Clearance Alert</option>
                <option value="Price Issue">Price / Stock Inaccuracy</option>
                <option value="Feature Request">Suggestion / Improvement</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">
                What are you experiencing? <span className="text-red-500">*</span>
              </label>
              <textarea
                required
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what happened, unexpected simulation behavior, or any issues..."
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs outline-none focus:border-emerald-600"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">
                Contact (Email / Discord) <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="you@email.com or @handle"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs outline-none"
              />
            </div>

            {/* Screenshot Attachment with Preview */}
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">
                Attach Screenshot <span className="text-slate-400 font-normal">(Optional, max 4MB)</span>
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleImageChange}
                className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
              />
              {imagePreview && (
                <div className="mt-2 relative inline-block">
                  <img src={imagePreview} alt="Preview" className="h-24 rounded-lg border border-slate-200 object-cover" />
                  <button
                    type="button"
                    onClick={() => { setImageFile(null); setImagePreview(null); }}
                    className="absolute -top-1.5 -right-1.5 bg-red-600 text-white rounded-full w-5 h-5 text-[10px] font-bold shadow-md"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>

            <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-[10px] text-slate-500">
              ℹ️ Your active PC build components will be attached automatically to help diagnose the exact hardware specs.
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow-sm transition disabled:opacity-60"
            >
              {isSubmitting ? "Submitting Report..." : "Submit Feedback"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}