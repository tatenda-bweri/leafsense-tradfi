// Dashboard JavaScript for LeafSense Options Analytics

// Global variables
let pauseUpdates = false;
let currentExpiryFilter = "All";
let darkMode = true;

// Initialize on document ready
$(document).ready(function () {
  // Initialize components
  initializeControls();
  initializeTradingViewWidget();

  // Load initial data
  loadMarketMetrics();
  loadGammaExposureData();

  // Set up refresh interval
  setInterval(refreshData, 60000); // Refresh every minute
});

// Initialize UI controls and event handlers
function initializeControls() {
  // Pause updates toggle
  $("#pauseUpdates").change(function () {
    pauseUpdates = $(this).prop("checked");
  });

  // Expiry filter dropdown
  $("#expiryFilter").change(function () {
    currentExpiryFilter = $(this).val();
    loadGammaExposureData();
  });

  // Dark mode toggle
  $("#dark-mode-toggle").click(function () {
    darkMode = !darkMode;
    $("body").attr("data-mode", darkMode ? "dark" : "light");
    updateTradingViewTheme();
    refreshCharts();
  });
}

// Load market metrics data
function loadMarketMetrics() {
  if (pauseUpdates) return;

  $.ajax({
    url: "/api/market-metrics",
    method: "GET",
    success: function (data) {
      updateMetricsDisplay(data);
    },
    error: function (error) {
      console.error("Error fetching market metrics:", error);
    },
  });
}

// Load gamma exposure data
function loadGammaExposureData() {
  if (pauseUpdates) return;

  $.ajax({
    url: "/api/gamma-exposure",
    method: "GET",
    data: {
      expiry_filter: currentExpiryFilter,
    },
    success: function (data) {
      drawGammaExposureChart(data);
    },
    error: function (error) {
      console.error("Error fetching gamma exposure data:", error);
    },
  });
}

// Update metrics display
function updateMetricsDisplay(data) {
  // Update value boxes with metrics data
  $("#metric-1-value").text(`$${data.spot_price} (${data.price_change_pct}%)`);
  // Update other metrics similarly
}

// Draw gamma exposure chart
function drawGammaExposureChart(data) {
  // Process data for Plotly
  const strikes = data.map((item) => item.strike_price);
  const gammaValues = data.map((item) => item.total_gamma);

  // Create colors based on gamma sign
  const colors = gammaValues.map((val) =>
    val >= 0 ? "rgba(0, 255, 0, 0.7)" : "rgba(255, 0, 0, 0.7)"
  );

  // Create horizontal bar chart with Plotly
  const plotData = [
    {
      y: strikes,
      x: gammaValues,
      type: "bar",
      orientation: "h",
      marker: {
        color: colors,
      },
      text: gammaValues.map((val) => val.toFixed(2)),
      textposition: "auto",
    },
  ];

  const layout = {
    title: "Gamma Exposure by Strike",
    xaxis: {
      title: "Gamma Exposure",
    },
    yaxis: {
      title: "Strike Price",
    },
    plot_bgcolor: darkMode ? "rgb(29, 32, 33)" : "white",
    paper_bgcolor: darkMode ? "rgb(29, 32, 33)" : "white",
    font: {
      color: darkMode ? "white" : "black",
    },
    margin: {
      l: 50,
      r: 30,
      t: 50,
      b: 30,
    },
  };

  Plotly.newPlot("gammaPlot", plotData, layout);
}

// Initialize Plotly bar chart
function initializePlotlyChart() {
  var data = [
    {
      x: ["A", "B", "C"],
      y: [20, 14, 23],
      type: "bar",
    },
  ];

  var layout = {
    title: "Market Metrics",
    xaxis: {
      title: "Categories",
    },
    yaxis: {
      title: "Values",
    },
  };

  Plotly.newPlot("plotly-chart", data, layout);
}

// Update Plotly chart theme
function updatePlotlyTheme() {
  var update = {
    paper_bgcolor: darkMode ? "black" : "white",
    plot_bgcolor: darkMode ? "black" : "white",
    font: {
      color: darkMode ? "white" : "black",
    },
  };

  Plotly.relayout("plotly-chart", update);
}

// Call the initialize function on page load
document.addEventListener("DOMContentLoaded", function () {
  initializePlotlyChart();
});

// Refresh all data
function refreshData() {
  if (!pauseUpdates) {
    loadMarketMetrics();
    loadGammaExposureData();
  }
}

// Refresh charts with current theme
function refreshCharts() {
  loadGammaExposureData();
}
