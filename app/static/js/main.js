// AI Assistant Handlers for Ticket Detail View
document.addEventListener("DOMContentLoaded", function () {
  // Urgency & Impact Live Priority Preview
  const urgencySelect = document.getElementById("urgency-select");
  const impactSelect = document.getElementById("impact-select");
  const priorityBadge = document.getElementById("priority-preview-badge");

  function updatePriorityPreview() {
    if (!urgencySelect || !impactSelect || !priorityBadge) return;
    const u = urgencySelect.value.toLowerCase();
    const i = impactSelect.value.toLowerCase();

    const matrix = {
      "low_low": "P4 (Low)",
      "low_medium": "P4 (Low)",
      "low_high": "P3 (Medium)",
      "medium_low": "P4 (Low)",
      "medium_medium": "P3 (Medium)",
      "medium_high": "P2 (High)",
      "high_low": "P3 (Medium)",
      "high_medium": "P2 (High)",
      "high_high": "P1 (Critical)",
    };

    const key = `${u}_${i}`;
    const p = matrix[key] || "P3 (Medium)";
    priorityBadge.textContent = `Calculated: ${p}`;

    priorityBadge.className = "badge mt-1 ";
    if (p.startsWith("P1")) priorityBadge.className += "bg-danger";
    else if (p.startsWith("P2")) priorityBadge.className += "bg-warning text-dark";
    else if (p.startsWith("P3")) priorityBadge.className += "bg-info text-dark";
    else priorityBadge.className += "bg-secondary";
  }

  if (urgencySelect && impactSelect) {
    urgencySelect.addEventListener("change", updatePriorityPreview);
    impactSelect.addEventListener("change", updatePriorityPreview);
    updatePriorityPreview();
  }

  // AI Buttons
  const btnSummarize = document.getElementById("btn-ai-summarize");
  const btnSuggest = document.getElementById("btn-ai-suggest");
  const btnDraft = document.getElementById("btn-ai-draft");
  const aiOutputBox = document.getElementById("ai-output-box");
  const aiOutputContent = document.getElementById("ai-output-content");
  const commentInput = document.getElementById("comment-body");

  async function callAIApi(endpoint, ticketNum, buttonElement) {
    if (!aiOutputBox || !aiOutputContent) return;
    const originalText = buttonElement.innerHTML;
    buttonElement.disabled = true;
    buttonElement.innerHTML = `<span class="spinner-border spinner-border-sm" role="status"></span> Thinking...`;

    aiOutputBox.classList.remove("d-none");
    aiOutputContent.innerHTML = `<div class="text-muted"><span class="spinner-border spinner-border-sm"></span> Processing ticket context with AI...</div>`;

    try {
      const response = await fetch(`/api/ai/${endpoint}/${ticketNum}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await response.json();
      if (data.success) {
        const text = data.summary || data.suggestions || data.draft || "";
        aiOutputContent.innerHTML = text.replace(/\n/g, "<br>");

        // If draft response, provide one-click insert into reply box
        if (data.draft && commentInput) {
          aiOutputContent.innerHTML += `
            <div class="mt-3">
              <button type="button" class="btn btn-sm btn-outline-primary" id="btn-insert-draft">
                <i class="bi bi-box-arrow-in-down"></i> Insert into Response Box
              </button>
            </div>
          `;
          document.getElementById("btn-insert-draft").onclick = () => {
            commentInput.value = data.draft;
            commentInput.scrollIntoView({ behavior: "smooth" });
          };
        }
      } else {
        aiOutputContent.innerHTML = `<span class="text-danger">Failed to generate AI output.</span>`;
      }
    } catch (err) {
      console.error(err);
      aiOutputContent.innerHTML = `<span class="text-danger">Network error connecting to AI service.</span>`;
    } finally {
      buttonElement.disabled = false;
      buttonElement.innerHTML = originalText;
    }
  }

  if (btnSummarize) {
    btnSummarize.addEventListener("click", () => {
      callAIApi("summarize", btnSummarize.dataset.ticket, btnSummarize);
    });
  }

  if (btnSuggest) {
    btnSuggest.addEventListener("click", () => {
      callAIApi("suggest-resolution", btnSuggest.dataset.ticket, btnSuggest);
    });
  }

  if (btnDraft) {
    btnDraft.addEventListener("click", () => {
      callAIApi("draft-response", btnDraft.dataset.ticket, btnDraft);
    });
  }
});
