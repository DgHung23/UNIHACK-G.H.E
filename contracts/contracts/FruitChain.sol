// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title FruitChain — chỉ lưu BẰNG CHỨNG (hash) của vòng đời lô trái cây.
/// eventHash được tính off-chain (SHA-256) và truyền vào dạng bytes32. Contract bắt buộc
/// tính liên tục của prevHash, kiểm tra quyền theo vai trò và đóng lô sau SOLD.
contract FruitChain {
    enum Role { NONE, ADMIN, FARMER, WAREHOUSE, TRANSPORT, DISTRIBUTOR, RETAILER, REGULATOR }
    enum EventType { HARVEST, HANDOFF, VIOLATION, SOLD, INSPECTION }

    struct BatchEvent {
        EventType eventType;
        address actor;
        string  actorId;
        string  toActorId;
        uint64  ts;
        bytes32 dataHash;
        bytes32 prevHash;
        bytes32 eventHash;
        uint32  rulCentiDays;   // RUL * 100
        bytes32 modelHash;
    }

    address public admin;
    mapping(address => Role) public roles;
    mapping(bytes32 => bool) public registeredModels;
    mapping(bytes32 => string) public modelVersions;
    mapping(bytes32 => BatchEvent[]) private _events;      // key = keccak256(bytes(batchId))
    mapping(bytes32 => string) private _custodians;
    mapping(bytes32 => mapping(bytes32 => bool)) private _recordedHashes;
    mapping(bytes32 => address) public actorWallets;

    event BatchEventRecorded(bytes32 indexed batchKey, string batchId, EventType eventType, bytes32 eventHash, uint64 ts);
    event ModelRegistered(bytes32 indexed modelHash, string version);
    event RoleGranted(address indexed account, Role role);
    event ActorRegistered(string actorId, address indexed wallet);

    // Bitmask vai trò được phép (ADMIN luôn được phép)
    uint256 private constant M_FARMER = 1 << uint8(Role.FARMER);
    uint256 private constant M_WAREHOUSE = 1 << uint8(Role.WAREHOUSE);
    uint256 private constant M_TRANSPORT = 1 << uint8(Role.TRANSPORT);
    uint256 private constant M_DISTRIBUTOR = 1 << uint8(Role.DISTRIBUTOR);
    uint256 private constant M_RETAILER = 1 << uint8(Role.RETAILER);
    uint256 private constant M_REGULATOR = 1 << uint8(Role.REGULATOR);
    uint256 private constant M_PARTICIPANTS = M_FARMER | M_WAREHOUSE | M_TRANSPORT | M_DISTRIBUTOR | M_RETAILER;

    modifier onlyRoles(uint256 mask) {
        Role r = roles[msg.sender];
        require(r == Role.ADMIN || (r != Role.NONE && (mask & (1 << uint8(r))) != 0), "forbidden");
        _;
    }

    constructor() { admin = msg.sender; roles[msg.sender] = Role.ADMIN; }

    function grantRole(address who, Role r) external {
        require(msg.sender == admin, "only admin");
        require(who != address(0), "zero address");
        require(who != admin || r == Role.ADMIN, "admin role required");
        roles[who] = r;
        emit RoleGranted(who, r);
    }

    function registerModel(bytes32 modelHash, string calldata version) external {
        require(roles[msg.sender] == Role.ADMIN, "only admin");
        require(modelHash != bytes32(0), "zero model hash");
        require(bytes(version).length > 0, "empty model version");
        require(!registeredModels[modelHash], "model already registered");
        registeredModels[modelHash] = true;
        modelVersions[modelHash] = version;
        emit ModelRegistered(modelHash, version);
    }

    function registerActor(string calldata actorId, address wallet) external {
        require(msg.sender == admin, "only admin");
        require(bytes(actorId).length > 0 && wallet != address(0), "invalid actor");
        bytes32 key = keccak256(bytes(actorId));
        require(actorWallets[key] == address(0), "actor already registered");
        actorWallets[key] = wallet;
        emit ActorRegistered(actorId, wallet);
    }

    function createBatch(string calldata batchId, string calldata farmId, uint64 ts, bytes32 metadataHash,
                         bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRoles(M_FARMER)
    {
        bytes32 k = keccak256(bytes(batchId));
        require(_events[k].length == 0, "batch exists");
        _append(k, batchId, EventType.HARVEST, farmId, "", ts, metadataHash, bytes32(0), eventHash, rulCentiDays, modelHash);
    }

    function recordHandoff(string calldata batchId, string calldata fromId, string calldata toId, uint64 ts,
                           bytes32 dataHash, bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRoles(M_PARTICIPANTS)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.HANDOFF, fromId, toId, ts, dataHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordViolation(string calldata batchId, string calldata actorId, uint64 ts, bytes32 evidenceHash,
                             bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRoles(M_PARTICIPANTS | M_REGULATOR)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.VIOLATION, actorId, "", ts, evidenceHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordSold(string calldata batchId, string calldata retailerId, uint64 ts, bytes32 dataHash,
                        bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRoles(M_RETAILER)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.SOLD, retailerId, "", ts, dataHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordInspection(string calldata batchId, string calldata actorId, uint64 ts, bytes32 imageHash,
                              bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRoles(M_PARTICIPANTS | M_REGULATOR)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.INSPECTION, actorId, "", ts, imageHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function getEventCount(string calldata batchId) external view returns (uint256) {
        return _events[keccak256(bytes(batchId))].length;
    }

    function getEvent(string calldata batchId, uint256 i) external view returns (BatchEvent memory) {
        return _events[keccak256(bytes(batchId))][i];
    }

    function headHash(string calldata batchId) external view returns (bytes32) {
        BatchEvent[] storage e = _events[keccak256(bytes(batchId))];
        return e.length == 0 ? bytes32(0) : e[e.length - 1].eventHash;
    }

    function currentActor(string calldata batchId) external view returns (string memory) {
        return _custodians[keccak256(bytes(batchId))];
    }

    function _append(bytes32 k, string memory batchId, EventType t, string memory actorId, string memory toId, uint64 ts,
                     bytes32 dataHash, bytes32 prevHash, bytes32 eventHash, uint32 rul, bytes32 modelHash) internal {
        BatchEvent[] storage e = _events[k];
        require(bytes(batchId).length > 0 && bytes(actorId).length > 0, "empty identifier");
        if (roles[msg.sender] != Role.ADMIN) {
            require(actorWallets[keccak256(bytes(actorId))] == msg.sender, "actor wallet mismatch");
        }
        require(eventHash != bytes32(0) && dataHash != bytes32(0), "zero evidence hash");
        require(!_recordedHashes[k][eventHash], "duplicate event hash");
        if (e.length > 0) {
            require(prevHash == e[e.length - 1].eventHash, "bad prevHash");
            require(e[e.length - 1].eventType != EventType.SOLD, "batch closed");
            require(ts >= e[e.length - 1].ts, "timestamp before head");
        } else {
            require(t == EventType.HARVEST, "batch not found");
        }
        require(modelHash == bytes32(0) || registeredModels[modelHash], "unknown model");
        if (t == EventType.HANDOFF || t == EventType.SOLD) {
            require(keccak256(bytes(actorId)) == keccak256(bytes(_custodians[k])), "wrong custodian");
        }
        if (t == EventType.HARVEST) _custodians[k] = actorId;
        if (t == EventType.HANDOFF) {
            require(bytes(toId).length > 0, "empty recipient");
            require(keccak256(bytes(toId)) != keccak256(bytes(actorId)), "same custodian");
            _custodians[k] = toId;
        }
        _recordedHashes[k][eventHash] = true;
        e.push(BatchEvent(t, msg.sender, actorId, toId, ts, dataHash, prevHash, eventHash, rul, modelHash));
        emit BatchEventRecorded(k, batchId, t, eventHash, ts);
    }
}
