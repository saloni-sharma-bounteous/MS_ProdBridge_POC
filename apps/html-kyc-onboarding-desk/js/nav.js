function renderNav() {
  var u = currentUser();
  var html = '<span class="brand">KYC Onboarding Desk</span>' +
    '<a href="index.html">Queue</a>' +
    '<a href="new-case.html">New customer</a>' +
    '<a href="screening.html">Screening</a>' +
    '<a href="reports.html">Reports</a>';
  if (u && u.role === "admin") html += '<a href="old-dashboard.html">Legacy</a>';
  html += '<span class="who">' + (u ? u.name + " (" + u.role + ") " : "") + '<a href="#" onclick="logout()">Sign out</a></span>';
  document.getElementById("nav").innerHTML = html;
}
