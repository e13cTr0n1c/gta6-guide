(function () {
  "use strict";

  var node = document.getElementById("tool-data");
  if (!node) {
    return;
  }

  var data = JSON.parse(node.textContent);

  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
    });
  });

  if (data.tool === "garage") {
    setupGarage(data);
  }
  if (data.tool === "money") {
    setupMoney(data);
  }
  if (data.tool === "cheats") {
    setupCheats(data);
  }

  function dollars(amount) {
    return "$" + amount.toLocaleString("en-GB");
  }

  function plural(count, one, many) {
    return count + " " + (count === 1 ? one : many);
  }

  function setupGarage(info) {
    var form = document.getElementById("garage-form");
    var costEl = document.getElementById("garage-cost");
    var countEl = document.getElementById("garage-count");
    var pcEl = document.getElementById("slots-pc");
    var gsEl = document.getElementById("slots-gs");
    if (!form || !costEl || !countEl || !pcEl || !gsEl) {
      return;
    }

    function update() {
      var listCount = 0;
      var cost = 0;
      var valentina = false;
      form.querySelectorAll("input[type='checkbox']").forEach(function (box) {
        if (!box.checked) {
          return;
        }
        if (box.getAttribute("data-kind") === "valentina") {
          valentina = true;
          return;
        }
        listCount += 1;
        var price = Number(box.getAttribute("data-price"));
        if (Number.isFinite(price)) {
          cost += price;
        }
      });

      costEl.textContent = dollars(cost);
      countEl.textContent = "Garages ticked from the list of 10: " + listCount + ".";

      var extra = listCount;
      var withStart = info.startSlots + extra;
      var pcLead;
      if (listCount === 0) {
        pcLead = "PC Gamer says each garage holds a single car. I have not ticked a list garage, so that reading adds 0 slots.";
      } else {
        pcLead =
          "PC Gamer says each garage holds a single car. On that reading the " +
          plural(listCount, "list garage", "list garages") +
          " I ticked " +
          (listCount === 1 ? "adds" : "add") +
          " " +
          plural(extra, "slot", "slots") +
          ".";
      }
      pcEl.textContent =
        pcLead +
        " With the " +
        info.startSlots +
        " starting slots, that reading is " +
        withStart +
        ". I am not folding Valentina's garage into this number, because GameSpot gives that garage its own slot count.";

      var gs =
        "GameSpot says the list garages hold one or a couple of vehicles, so I will not turn those " +
        listCount +
        " garages into one slot total. GameSpot's exact figures on this form are the " +
        info.startSlots +
        " starting slots";
      if (valentina) {
        gs +=
          ", plus " +
          info.valentinaSlots +
          " slots for Valentina's Ocean Beach garage. Those two exact figures together are " +
          (info.startSlots + info.valentinaSlots) +
          ", before the list garages.";
      } else {
        gs +=
          ". Valentina's Ocean Beach garage is " +
          info.valentinaSlots +
          " slots in GameSpot's account, and I have not ticked it.";
      }
      gs += " GameSpot also says 12 or more slots are possible. That line is theirs, not a total I calculated from the ticks.";
      gsEl.textContent = gs;
    }

    form.addEventListener("change", update);
    var clear = document.getElementById("garage-clear");
    if (clear) {
      clear.addEventListener("click", function () {
        form.querySelectorAll("input[type='checkbox']").forEach(function (box) {
          box.checked = false;
        });
        update();
      });
    }
    update();
  }

  function setupMoney(info) {
    var form = document.getElementById("money-form");
    var list = document.getElementById("money-list");
    var garageLine = document.getElementById("money-garage");
    if (!form || !list || !garageLine) {
      return;
    }

    function update() {
      list.replaceChildren();
      var any = false;
      form.querySelectorAll("input[name='activity']").forEach(function (box) {
        if (!box.checked) {
          return;
        }
        any = true;
        var index = Number(box.value);
        var activity = info.activities[index];
        var item = document.createElement("li");
        var title = document.createElement("strong");
        title.textContent = activity.activity;
        var wording = document.createElement("p");
        wording.textContent = "Published wording: " + activity.payout;
        var when = document.createElement("p");
        when.textContent = "When the guides place it: " + activity.when;
        var outlet = document.createElement("p");
        outlet.textContent = "Outlet: " + activity.outlet;
        item.append(title, wording, when, outlet);
        list.appendChild(item);
      });
      if (!any) {
        var empty = document.createElement("li");
        empty.textContent = "No activities ticked yet. The ranges stay as published wording. I will not add them into a sum.";
        list.appendChild(empty);
      }

      var selected = form.querySelector("input[name='target']:checked");
      if (!selected || selected.value === "") {
        garageLine.textContent =
          "No garage selected. Pocket cash still stops at " +
          dollars(info.cashCap) +
          ", and a purchase over " +
          dollars(info.cashPurchaseLimit) +
          " goes through BuckMe.";
        return;
      }
      var price = Number(selected.getAttribute("data-price"));
      var name = selected.getAttribute("data-name");
      var sentence = name + " is listed at " + (price === 0 ? "Free" : dollars(price)) + ". ";
      if (price === 0) {
        sentence += "I have nothing to compare with the cash cap, because the published price is free.";
      } else if (price <= info.cashPurchaseLimit) {
        sentence += "That price sits within the " + dollars(info.cashPurchaseLimit) + " cash purchase limit in the guides.";
      } else {
        sentence +=
          "That price is over " +
          dollars(info.cashPurchaseLimit) +
          ", so the guides say pocket cash will not cover it. It goes through BuckMe.";
        if (price > info.cashCap) {
          sentence += " It is also over the " + dollars(info.cashCap) + " pocket cash cap.";
        }
      }
      sentence += " I am not turning the payout ranges into a count.";
      garageLine.textContent = sentence;
    }

    form.addEventListener("change", update);
    var clear = document.getElementById("money-clear");
    if (clear) {
      clear.addEventListener("click", function () {
        form.querySelectorAll("input[name='activity']").forEach(function (box) {
          box.checked = false;
        });
        var none = form.querySelector("input[name='target'][value='']");
        if (none) {
          none.checked = true;
        }
        update();
      });
    }
    update();
  }

  function setupCheats(info) {
    var input = document.getElementById("cheat-q");
    var out = document.getElementById("cheat-result");
    if (!input || !out) {
      return;
    }

    function showCheat(cheat) {
      var article = document.createElement("article");
      article.className = "card";
      var title = document.createElement("p");
      var strong = document.createElement("strong");
      strong.textContent = cheat.name;
      title.appendChild(strong);
      var code = document.createElement("p");
      code.textContent = "Code: " + cheat.code;
      var unlock = document.createElement("p");
      unlock.textContent = "Unlock: " + cheat.unlock;
      var notes = document.createElement("p");
      notes.textContent = cheat.notes;
      article.append(title, code, unlock, notes);
      return article;
    }

    function render() {
      var query = input.value.trim().toLowerCase();
      out.replaceChildren();
      var hits = info.cheats.filter(function (cheat) {
        var blob = (cheat.name + " " + cheat.code + " " + cheat.unlock + " " + cheat.notes).toLowerCase();
        return query === "" || blob.indexOf(query) !== -1;
      });
      if (!hits.length) {
        var empty = document.createElement("p");
        empty.textContent = "Nothing in the sourced list matches that. Many codes are still unknown, and I will not fill the gaps.";
        out.appendChild(empty);
        return;
      }
      hits.forEach(function (cheat) {
        out.appendChild(showCheat(cheat));
      });
    }

    input.addEventListener("input", render);
  }
})();
