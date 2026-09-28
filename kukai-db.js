import { initializeApp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import {
  getFirestore,
  doc,
  collection,
  setDoc,
  updateDoc,
  getDoc,
  onSnapshot,
  serverTimestamp,
  query,
  orderBy,
} from "https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const ROOMS = "haikuRooms";

const CODE_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"; // 紛らわしい文字(0,1,O,I)を除外

function generateRoomCode() {
  let code = "";
  for (let i = 0; i < 5; i++) {
    code += CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)];
  }
  return code;
}

export function newParticipantId() {
  // crypto.randomUUID はセキュアコンテキスト（HTTPS/localhost）限定のため、
  // 同一Wi-Fi内のLAN IP(http://192.168.x.x)からのアクセスではフォールバックが必要。
  if (window.crypto && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function createRoom(hostId) {
  let code = generateRoomCode();
  for (let i = 0; i < 5; i++) {
    const snap = await getDoc(doc(db, ROOMS, code));
    if (!snap.exists()) break;
    code = generateRoomCode();
  }
  await setDoc(doc(db, ROOMS, code), {
    status: "waiting",
    hostId,
    prompt: null,
    createdAt: serverTimestamp(),
  });
  return code;
}

export async function getRoom(roomId) {
  const snap = await getDoc(doc(db, ROOMS, roomId));
  return snap.exists() ? snap.data() : null;
}

export async function updateRoom(roomId, fields) {
  await updateDoc(doc(db, ROOMS, roomId), fields);
}

export async function joinRoom(roomId, participantId, name, emoji) {
  await setDoc(doc(db, ROOMS, roomId, "participants", participantId), {
    name,
    emoji,
    text1: null,
    submitted1: false,
    ai1: null,
    card: null,
    text2: null,
    submitted2: false,
    ai2: null,
    joinedAt: serverTimestamp(),
  });
}

export async function updateParticipant(roomId, participantId, fields) {
  await updateDoc(doc(db, ROOMS, roomId, "participants", participantId), fields);
}

export async function advanceRoomStatus(roomId, from, to) {
  // 条件成立を検知した全員が呼びうる。多重実行されても実害はない。
  const snap = await getDoc(doc(db, ROOMS, roomId));
  if (snap.exists() && snap.data().status === from) {
    await updateDoc(doc(db, ROOMS, roomId), { status: to });
  }
}

export async function submitPraise(roomId, raterId, targetId, points, comment) {
  await setDoc(doc(db, ROOMS, roomId, "praises", `${raterId}_${targetId}`), {
    raterId,
    targetId,
    points,
    comment,
    praisedAt: serverTimestamp(),
  });
}

export function subscribeRoom(roomId, cb) {
  return onSnapshot(doc(db, ROOMS, roomId), (snap) => {
    cb(snap.exists() ? snap.data() : null);
  });
}

export function subscribeParticipants(roomId, cb) {
  const q = query(collection(db, ROOMS, roomId, "participants"), orderBy("joinedAt", "asc"));
  return onSnapshot(q, (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}

export function subscribePraises(roomId, cb) {
  return onSnapshot(collection(db, ROOMS, roomId, "praises"), (snap) => {
    cb(snap.docs.map((d) => d.data()));
  });
}
