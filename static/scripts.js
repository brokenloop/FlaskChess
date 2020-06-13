var board,
  game = new Chess(),
  statusEl = $('#status'),
  fenEl = $('#fen'),
  pgnEl = $('#pgn');


// update the board position after the piece snap
// for castling, en passant, pawn promotion
var onSnapEnd = function() {
    board.position(game.fen());
};

var updateStatus = function() {
  var status = '';

  var moveColor = 'White';
  if (game.turn() === 'b') {
    moveColor = 'Black';
  }

  // checkmate?
  if (game.in_checkmate() === true) {
    status = 'Game over, ' + moveColor + ' is in checkmate.';
  }

  // draw?
  else if (game.in_draw() === true) {
    status = 'Game over, drawn position';
  }

  // game still on
  else {
    status = moveColor + ' to move';

    // check?
    if (game.in_check() === true) {
      status += ', ' + moveColor + ' is in check';
    }
  }

  setStatus(status);
  getLastCapture();
  createTable();
  //updateScroll();

  console.log(game.fen());
  statusEl.html(status);
  fenEl.html(game.fen());
  pgnEl.html(game.pgn());
};

var cfg = {
  draggable: true,
  position: 'start',
  onSnapEnd: onSnapEnd
};

/*
var getResponseMove = function() {
    var e = document.getElementById("sel1");
    var depth = e.options[e.selectedIndex].value;
    fen = game.fen()
    $.get($SCRIPT_ROOT + "/move/" + depth + "/" + fen, function(data) {
        game.move(data, {sloppy: true});
        updateStatus();
        // This is terrible and I should feel bad. Find some way to fix this properly.
        // The animations would stutter when moves were returned too quick, so I added a 100ms delay before the animation
        setTimeout(function(){ board.position(game.fen()); }, 100);
    })
}
*/


// did this based on a stackoverflow answer
// http://stackoverflow.com/questions/29493624/cant-display-board-whereas-the-id-is-same-when-i-use-chessboard-js
setTimeout(function() {
    board = ChessBoard('board', cfg);
//    updateStatus();
}, 0);


var setPGN = function() {
  var table = document.getElementById("pgn");

  var pgn = game.pgn().split(" ");
    var move = pgn[pgn.length - 1];
}

var createTable = function() {

    var pgn = game.pgn().split(" ");

    var data = [];

    for (i = 0; i < pgn.length; i += 3) {
        var index = i / 3;
        data[index] = {};
        for (j = 0; j < 3; j++) {
            var label = "";
            if (j === 0) {
                label = "moveNumber";
            } else if (j === 1) {
                label = "whiteMove";
            } else if (j === 2) {
                label = "blackMove";
            }
            if (pgn.length > i + j) {
                data[index][label] = pgn[i + j];
            } else {
                data[index][label] = "";
            }
        }
    }

    $('#pgn tr').not(':first').not(':last').remove();
    var html = '';
    for (var i = 0; i < data.length; i++) {
                html += '<tr><td>' + data[i].moveNumber + '</td><td>'
                + data[i].whiteMove + '</td><td>'
                + data[i].blackMove + '</td></tr>';
    }

    $('#pgn tr').first().after(html);
}

var updateScroll = function() {
    $('#moveTable').scrollTop($('#moveTable')[0].scrollHeight);
}

var setStatus = function(status) {
  document.getElementById("status").innerHTML = status;
}

var update = function(data) {

    console.log("Data from server = " + data);

    var lines = data.split("\n");
    var action = lines[0];
    var move_history, notes;

    if ("finished" === action) {
      notes = "<h1>Finished</h1>" + lines[1];
    } else if (["position", "rewind"].includes(action)) {
      
      // Find the FEN in line 2
      fen = lines[1]
      moves = lines[2];
      notes = lines[3];

      console.log(notes);
      // Reset the board with Forsyth-Edwards notation
      board.position(fen);

      $('#moves').html(moves)
      var rewind = ""
      
      if ("rewind" === action) {
        $('#rewind').show()
      } else {
        $('#rewind').hide()
      }
    } else {
      alert("Unknown action!")
    }
    $('#notes').html(notes);
}

var nextMove = function() {
  $.get($SCRIPT_ROOT + "/next", update)
}

var previousMove = function() {
  $.get($SCRIPT_ROOT + "/previous", update)
}

var resetMoves = function() {
  $.get($SCRIPT_ROOT + "/reset", update)
}

var getCapturedPieces = function() {
    var history = game.history({ verbose: true });
    for (var i = 0; i < history.length; i++) {
        if ("captured" in history[i]) {
            console.log(history[i]["captured"]);
        }
    }
}

var getLastCapture = function() {
  
    var history = game.history({ verbose: true });
    var index = history.length - 1;

    if ("captured" in history[index]) {
        console.log(history[index]["captured"]);
    }
}
