// TrackWell shared front-end behaviour (small and framework-free).
(function () {
  "use strict";

  // Confirmation dialogs for destructive forms: <form data-confirm="message">
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (form.dataset && form.dataset.confirm) {
      if (!window.confirm(form.dataset.confirm)) {
        ev.preventDefault();
        return;
      }
    }
    // Loading feedback: disable submit button and show spinner for slow actions.
    var btn = form.querySelector("button[type=submit][data-loading]");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' +
        btn.dataset.loading;
    }
  });

  // Auto-dismiss success flashes after a few seconds.
  document.querySelectorAll(".alert[data-autodismiss]").forEach(function (el) {
    setTimeout(function () {
      var alert = bootstrap.Alert.getOrCreateInstance(el);
      alert.close();
    }, 6000);
  });

  // Shared chart defaults.
  if (window.Chart) {
    Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = "#4b5563";
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
  }

  window.TrackWell = {
    riskColors: { High: "#b23a48", Medium: "#b8741a", Low: "#2e7d4f", None: "#aab4c0" },
    riskDistributionChart: function (canvasId, counts, unpredicted) {
      var el = document.getElementById(canvasId);
      if (!el || !window.Chart) return;
      var labels = ["High Risk", "Medium Risk", "Low Risk"];
      var data = [counts.High || 0, counts.Medium || 0, counts.Low || 0];
      var colors = [this.riskColors.High, this.riskColors.Medium, this.riskColors.Low];
      if (unpredicted) { labels.push("Not predicted"); data.push(unpredicted); colors.push(this.riskColors.None); }
      new Chart(el, {
        type: "doughnut",
        data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderWidth: 1 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: "62%",
          plugins: { legend: { position: "right" } } }
      });
    },
    classRiskChart: function (canvasId, rows) {
      var el = document.getElementById(canvasId);
      if (!el || !window.Chart || !rows.length) return;
      new Chart(el, {
        type: "bar",
        data: {
          labels: rows.map(function (r) { return r.class_name; }),
          datasets: [
            { label: "High", data: rows.map(function (r) { return r.high || 0; }), backgroundColor: this.riskColors.High },
            { label: "Medium", data: rows.map(function (r) { return r.medium || 0; }), backgroundColor: this.riskColors.Medium },
            { label: "Low", data: rows.map(function (r) { return r.low || 0; }), backgroundColor: this.riskColors.Low }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } }
      });
    },
    attendanceChart: function (canvasId, bands) {
      var el = document.getElementById(canvasId);
      if (!el || !window.Chart) return;
      new Chart(el, {
        type: "bar",
        data: { labels: ["Below 65%", "65-75%", "75% and above"],
          datasets: [{ label: "Students", data: [bands.low || 0, bands.borderline || 0, bands.good || 0],
            backgroundColor: [this.riskColors.High, this.riskColors.Medium, this.riskColors.Low] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 } } } }
      });
    },
    scoreTrendChart: function (canvasId, points) {
      var el = document.getElementById(canvasId);
      if (!el || !window.Chart || points.length < 2) return;
      new Chart(el, {
        type: "line",
        data: { labels: points.map(function (p) { return p.label; }),
          datasets: [{ label: "Score (%)", data: points.map(function (p) { return p.score; }),
            borderColor: "#2b7a9e", backgroundColor: "rgba(43,122,158,0.12)", tension: 0.25, fill: true, pointRadius: 3 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { y: { min: 0, max: 100 } } }
      });
    },
    importanceChart: function (canvasId, items) {
      var el = document.getElementById(canvasId);
      if (!el || !window.Chart || !items.length) return;
      new Chart(el, {
        type: "bar",
        data: { labels: items.map(function (i) { return i.label; }),
          datasets: [{ label: "Relative importance", data: items.map(function (i) { return Math.round(i.importance * 1000) / 10; }),
            backgroundColor: "#2b7a9e" }] },
        options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, title: { display: true, text: "% of total importance" } } } }
      });
    }
  };
})();
