// simple login - TODO replace with SSO later
var USERS = [
  { u: "analyst1",    p: "Welcome1",         role: "analyst" },
  { u: "senior1",     p: "Welcome1",         role: "senior_analyst" },
  { u: "compliance1", p: "Compliance#2025",  role: "compliance_officer" },
  { u: "admin",       p: "admin",            role: "admin" }
];

function login(u, p) {
  for (var i = 0; i < USERS.length; i++) {
    if (USERS[i].u === u && USERS[i].p === p) {
      sessionStorage.setItem("user", JSON.stringify({ name: u, role: USERS[i].role }));
      return true;
    }
  }
  return false;
}

function currentUser() {
  var raw = sessionStorage.getItem("user");
  return raw ? JSON.parse(raw) : null;
}

function requireLogin() {
  if (!currentUser()) { window.location.href = "login.html"; }
}

function logout() {
  sessionStorage.clear();
  window.location.href = "login.html";
}
