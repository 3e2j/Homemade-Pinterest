/** UI status state */
export const STATUS = {
  IDLE: "idle",
  LOADING_INITIAL: "loading_initial",
  LOADING_MORE: "loading_more",
  REFRESHING: "refreshing",
  ERROR: "error",
};

let currentStatus = STATUS.IDLE;
let statusMessage = "";
let statusListeners = [];

export function setStatus(status, message = "") {
  currentStatus = status;
  statusMessage = message;
  notifyListeners();
}

export function getStatus() {
  return { status: currentStatus, message: statusMessage };
}

export function onStatusChange(callback) {
  statusListeners.push(callback);
  return () => {
    statusListeners = statusListeners.filter((cb) => cb !== callback);
  };
}

function notifyListeners() {
  statusListeners.forEach((cb) =>
    cb({ status: currentStatus, message: statusMessage }),
  );
}
