# Governance

Stop the affected workstream if implementation requires:

- distributing or modifying Polar SDK source;
- transcribing SDK schemas, descriptors, enums, or generated bindings;
- independently parsing, decompressing, or decrypting REC content;
- sending a secret through argv, unsafe environment, logs, manifests, or output;
- accepting unversioned SDK-shaped output as the public schema;
- uploading SDK-derived or private material to public infrastructure.

Completion requires every tracker item, public synthetic gate, protected
contract, architecture build, restricted-artifact audit, and documentation
update to pass on one integration commit.
