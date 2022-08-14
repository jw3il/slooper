// the current state
var state = null;
// time where last state has been received
var stateTime = null;
// the currently rendered state
var renderedState = null;
// whether the state has been modified and is updating
var dirtyState = false;
// next key for new recordings
var nextKey = null;
// HTML dict of all recording rows
var rows = {};

function update() {
    // block parallel update calls
    if (typeof update.busy === 'undefined' ) {
        update.busy = false;
    }

    if (update.busy) {
        return;
    }

    update.busy = true;
    dirtyState = true;

    // get status and update DOM
    $.get("/status", function(data) {
        state = JSON.parse(data);
        stateTime = new Date();
        // get new key
        const keys = Object.keys(state.recordings);
        if (keys.length > 0) {
            nextKey = Math.max(...Object.keys(state.recordings).map(Number)) + 1;
        }
        else {
            nextKey = 0;
        }
        updateRecordingsTable();
        dirtyState = false;
        update.busy = false;
    }).fail(function() {
        update.busy = false;
    });
}

function createRow(key, recording) {
    const [time, length] = calcRecordingStats(recording);
    var row = document.createElement("tr");
    row.key = key;
    row.innerHTML = `
        <td></td>
        <td></td>
        <td></td> 
        <td>${time.toFixed(2)}</td>
        <td style="text-align: center;"><input type="range" min="0" max="1" value="${time / length}" step="any" key='${key}'></td>
        <td>${length.toFixed(2)}</td>
        <td><button type='button' class="btn btn-dark btn-sm" name='loopKeyButton' key='${key}'></button></td>
        <td><form method="get" action="/download/${key}"><button type="submit" class="btn btn-dark btn-sm"><i class="fa fa-download" aria-hidden="true"></i></button></form></td>
        <td><button type='button' class="btn btn-dark btn-sm" name='deleteButton' key='${key}'><i class="fa fa-trash" aria-hidden="true"></i></button>`;
    return $(row);
}

function createFullWidthRow(text) {
    var row = document.createElement("tr");
    row.innerHTML = `<td colspan='9'>${text}</td>`
    return $(row);
}

function updateHTMLifChanged(elem, html) {
    if (elem.html() == html)
        return;

    elem.html(html);
}

function calcRecordingStats(recording) {
    var length = recording.length / state.stream.samplerate;
    var time = recording.frame / state.stream.samplerate;
    if (recording.state == 'record') {
        // get current length
        length += (new Date() - stateTime) / 1000;
    }
    if (recording.state == 'loop') {
        // get current time
        time += (new Date() - stateTime) / 1000;
        time = time % length;
    }
    return [time, length]
}

function updateRecordingsTable() {
    if (state == null) {
        return;
    }

    if (state.stream.active) {
        if (renderedState != null && !renderedState.stream.active) {
            // clear table
            $("#recordings > tbody").html('');
        }
        $("#stream").html(`
            ${state.stream.samplerate} Hz | 
            device ${state.stream.device} |
            ${(state.stream.duration_stats.mean * 1000).toFixed(2)} ± ${(state.stream.duration_stats.std * 1000).toFixed(2)} ms 
            (99p: ${(state.stream.duration_stats['99p'] * 1000).toFixed(2)},
            max: ${(state.stream.duration_stats['max'] * 1000).toFixed(2)})
        `);
    }
    else {
        $("#stream").html(`<b>not active</b>`);
        $("#recordings > tbody").html(createFullWidthRow(state.stream.debug.join("<br>")));
        rows = {};
        return;
    }

    // new keys in the state => add
    var newKeys = [];
    // unused keys in the rows => remove
    var unusedKeys = Object.keys(rows);
    for (const key of Object.keys(state.recordings)) {
        if (key in rows) {
            unusedKeys.splice(unusedKeys.indexOf(key), 1);
        }
        else {
            newKeys.push(key);
        }
    }

    // remove unused rows from DOM
    for (const key of unusedKeys) {
        rows[key].remove();
        delete rows[key];
    }

    // create new rows
    for (const key of newKeys) {
        rows[key] = createRow(key, state.recordings[key]);
        $("#recordings > tbody").append(rows[key]);
    }

    // update table values
    for (const [key, recording] of Object.entries(state.recordings)) {
        var lastRecording = renderedState == null ? null : renderedState.recordings[key];
        if (typeof lastRecording === 'undefined') {
            lastRecording = null;
        }

        const [time, length] = calcRecordingStats(recording);

        // update values
        var row = rows[key];
        const id = key + (recording.name == '' ? '' : ':' + recording.name);
        updateHTMLifChanged($("td:nth-child(1)", row), `${id}`);
        updateHTMLifChanged($("td:nth-child(2)", row), `${recording.state}`);
        updateHTMLifChanged($("td:nth-child(3)", row), `${recording.volume}`);
        updateHTMLifChanged($("td:nth-child(4)", row), `${time.toFixed(2)}`);
        if (recording.state != 'pause' && $('td:nth-child(5) > input:hover').length == 0) {
            $("td:nth-child(5) > input", row).val(time / length);
        }
        updateHTMLifChanged($("td:nth-child(6)", row), `${length.toFixed(2)}`);
        if (lastRecording == null || lastRecording.state != recording.state) {
            const buttonHTML = recording.state == 'loop' ? '<i class="fa fa-pause" aria-hidden="true"></i>' : '<i class="fa fa-play" aria-hidden="true"></i>'
            updateHTMLifChanged($("td > button[name='loopKeyButton']", row), buttonHTML);
        }
    }

    renderedState = state;
}

function setPlaybackTime(key, time) {
    // set frame
    const frame = Math.floor(time * (state.recordings[key].length - 1));
    $.get("/set-frame/" + key + "/" + frame, function() {
        update();
    });
}

$('#recordings').on('click', "tbody > tr > td > button[name='loopKeyButton']", function(e) {
    e.preventDefault();
    const targetKey = $(e.target).closest('button').attr('key');
    loopKey(targetKey);
});

$('#recordings').on('click', "tbody > tr > td > button[name='deleteButton']", function(e) {
    e.preventDefault();
    const targetKey = $(e.target).closest('button').attr('key');
    deleteKey(targetKey);
});

$('#recordings').on('click touchend', "tbody > tr > td > input[type='range']", function(e) {
    e.preventDefault();
    setPlaybackTime($(e.target).attr('key'), $(e.target).val());
});

function loopKey(key) {
    if (dirtyState) {
        return;
    }

    const recordingState = state.recordings[key].state;
    if (recordingState == "pause") {
        $.get("/loop/" + key, function( data ) {
            update();
        });
    }
    else if (recordingState == "loop") {
        $.get("/pause/" + key, function( data ) {
            update();
        });
    }
}

function deleteKey(key) {
    if (dirtyState) {
        return;
    }

    $.get("/delete/" + key, function(data) {
        update();
    });
}

function pauseAll() {
    $.get("/pause", function(data) {
        update();
    });
}

function poweroff() {
    Swal.fire({
        title: 'Shutdown looper',
        text: "Are you sure you want to shut down?",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'No, I am not done yet.',
        cancelButtonText: "Yes, shut down!",
        }).then((result) => {
            if (!result.isConfirmed) {
                $.get("/poweroff", function(data) {});
        }
    })
}

var currentRecordingKey = null;
var loopAfterRecord = false;
var isRecording = false;

$("#record").click(function(){
    if (isRecording) {
        recordStop();
    }
    else {
        loopAfterRecord = ($("#autoLoopCheckbox").is(':checked'));
        recordStart();
    }
});

var recordHTML = "Record<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
var recordStopHTML = "Stop Recording<br>(<i class=\"fa fa-keyboard-o\"></i> space)"
$("#record").html(recordHTML);

function recordStart() {
    if (currentRecordingKey != null) {
        return;
    }
    const key = nextKey;
    currentRecordingKey = key;
    const name = $('input[id="recordName"]').val();
    $('input[id="recordName"]').val("");
    // TODO: Error handling...
    $.get("/delete/" + key, function(data) {
        if (name != '') {
            $.get("/set-name/" + key + "/" + name, function() {});
        }
        $.get("/record/" + key, function(data) {
            // we started recording
            isRecording = true;
            $("#record").html(recordStopHTML);
            $("#record").removeClass("btn-primary").addClass("btn-success");
            update();
        });
    });
}

function recordStop() {
    if (currentRecordingKey == null) {
        return;
    }
    const key = currentRecordingKey;
    const action = loopAfterRecord ? "/loop/" : "/pause/";
    $.get(action + key, function(data) {
        // we stopped recording
        isRecording = false;
        $("#record").html(recordHTML);
        $("#record").removeClass("btn-success").addClass("btn-primary");
        update();
        currentRecordingKey = null;
    });
}

$('body').keyup(function(e){
    // space
    if(e.keyCode == 32){
        if (currentRecordingKey == null) {
            loopAfterRecord = true;
            recordStart();
        }
        else {
            recordStop();
        }
    }
});

setInterval(() => {
    updateRecordingsTable();
}, 50);

setInterval(() => {
    update();
}, 2500);

update();
