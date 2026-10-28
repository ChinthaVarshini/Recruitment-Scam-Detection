import { useState } from "react";

const CHECKLIST_ITEMS = [
  "I found the employer's official website independently and confirmed the role is listed there.",
  "I checked that the recruiter email domain matches the employer's official domain.",
  "I will not pay registration, interview, training, equipment, or job-placement fees.",
  "I will not share passwords, one-time codes, bank PINs, or sensitive identity details with a recruiter.",
  "I verified the interview process and recruiter using contact details from the employer's official site.",
  "The job title, responsibilities, location, and salary are clear and consistent in the written offer.",
  "I checked the application link's domain before entering personal information.",
];

function readChecklist(storageKey) {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  } catch {
    return {};
  }
}

function SafeApplicationChecklist({ storageKey }) {
  const [checkedItems, setCheckedItems] = useState(() => readChecklist(storageKey));
  const [storageError, setStorageError] = useState("");
  const completedCount = CHECKLIST_ITEMS.reduce(
    (count, _item, index) => count + (checkedItems[index] ? 1 : 0),
    0,
  );

  const updateCheckedItem = (index, isChecked) => {
    const nextCheckedItems = {
      ...checkedItems,
      [index]: isChecked,
    };
    setCheckedItems(nextCheckedItems);
    try {
      localStorage.setItem(storageKey, JSON.stringify(nextCheckedItems));
      setStorageError("");
    } catch (error) {
      setStorageError(`Could not save checklist progress: ${error.message}`);
    }
  };

  return (
    <section className="result-section safe-checklist" aria-labelledby="safe-checklist-title">
      <div className="checklist-heading">
        <div>
          <h4 id="safe-checklist-title">Safe application checklist</h4>
          <p>Verify these items yourself before sharing details or accepting an offer.</p>
        </div>
        <strong>{completedCount}/{CHECKLIST_ITEMS.length} checked</strong>
      </div>
      <div className="checklist-items">
        {CHECKLIST_ITEMS.map((item, index) => (
          <label className="checklist-item" key={item}>
            <input
              type="checkbox"
              checked={Boolean(checkedItems[index])}
              onChange={(event) => updateCheckedItem(index, event.target.checked)}
            />
            <span>{item}</span>
          </label>
        ))}
      </div>
      {storageError && <p className="admin-error" role="alert">{storageError}</p>}
      <p className="checklist-disclaimer">
        Checklist completion does not change the model score or guarantee that a job is legitimate.
      </p>
    </section>
  );
}

export default SafeApplicationChecklist;
