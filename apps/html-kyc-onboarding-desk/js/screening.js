var SANCTIONS = ["ivan petrov", "kim jong chol", "ali reza mohammadi", "hassan al-demir", "viktor sokolov"];
var PEP_LIST = ["elena vasquez-ruiz", "jean-marc dupuis", "adaobi nwosu"];

// returns {sanctioned, pep}
function screenName(name) {
  var n = (name || "").toLowerCase();
  var res = { sanctioned: false, pep: false };
  SANCTIONS.forEach(function (s) { if (n.indexOf(s) > -1) res.sanctioned = true; });
  PEP_LIST.forEach(function (p) { if (n.indexOf(p) > -1) res.pep = true; });
  return res;
}
