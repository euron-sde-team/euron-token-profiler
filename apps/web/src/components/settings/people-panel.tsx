"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CopyField } from "@/components/copy-field";
import { RelativeTime } from "@/components/domain/relative-time";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { ErrorNotice, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ROLE } from "@/lib/labels";
import { useCreateUser, useMe, useUpdateUser, useUsers } from "@/lib/queries";
import type { Role, UserCreated } from "@/lib/types";

function AddPersonDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateUser({ silent: true });
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [created, setCreated] = useState<UserCreated | null>(null);

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setCreated(null);
      setEmail("");
      setName("");
      create.reset();
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      {created ? (
        <DialogContent title="Person added" description="Share this temporary password privately. It is shown once.">
          <CopyField value={created.temporary_password} label="Temporary password" />
          <DialogFooter>
            <Button onClick={() => close(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      ) : (
        <DialogContent title="Add a person" description="They sign in with the email and a temporary password.">
          <div className="space-y-4">
            <Field label="Name" htmlFor="person-name">
              <Input id="person-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
            </Field>
            <Field label="Email" htmlFor="person-email">
              <Input id="person-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
            </Field>
            <Field label="Role" htmlFor="person-role" hint={ROLE[role].description}>
              <NativeSelect id="person-role" value={role} onChange={(event) => setRole(event.target.value as Role)}>
                {(Object.keys(ROLE) as Role[]).map((key) => (
                  <option key={key} value={key}>
                    {ROLE[key].label}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            {create.error ? <ErrorNotice message={create.error.message} /> : null}
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button
              loading={create.isPending}
              disabled={!name.trim() || !email.trim()}
              onClick={async () => {
                try {
                  setCreated(await create.mutateAsync({ email: email.trim(), name: name.trim(), role }));
                } catch {
                  // Rendered above.
                }
              }}
            >
              Add person
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}

export function PeoplePanel() {
  const users = useUsers();
  const me = useMe();
  const update = useUpdateUser();
  const [adding, setAdding] = useState(false);
  if (users.error) return <ErrorState message={users.error.message} onRetry={() => users.refetch()} />;
  if (!users.data) return <Skeleton className="h-64" />;
  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-muted-foreground text-[13px]">Everyone who can sign in. Role changes apply at once.</p>
        <Button onClick={() => setAdding(true)}>
          <Plus /> Add person
        </Button>
      </div>
      <TableContainer label="People">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Person</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Active</TableHead>
              <TableHead className="text-right">Last sign-in</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.data.items.map((person) => {
              const self = person.id === me.data?.id;
              return (
                <TableRow key={person.id}>
                  <TableCell>
                    <span className="font-medium">{person.name}</span> {self ? <Badge tone="primary">You</Badge> : null}
                    <span className="text-muted-foreground block text-xs">{person.email}</span>
                  </TableCell>
                  <TableCell>
                    <NativeSelect
                      aria-label={`Role of ${person.name}`}
                      className="h-8 w-32 text-[13px]"
                      value={person.role}
                      disabled={self}
                      onChange={async (event) => {
                        await update.mutateAsync({ id: person.id, role: event.target.value as Role });
                        toast.success(`${person.name} is now ${ROLE[event.target.value as Role].label.toLowerCase()}`);
                      }}
                    >
                      {(Object.keys(ROLE) as Role[]).map((key) => (
                        <option key={key} value={key}>
                          {ROLE[key].label}
                        </option>
                      ))}
                    </NativeSelect>
                  </TableCell>
                  <TableCell>
                    <Switch
                      aria-label={`${person.name} is active`}
                      checked={person.is_active}
                      disabled={self}
                      onCheckedChange={(checked) => update.mutate({ id: person.id, is_active: checked })}
                    />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-right">
                    <RelativeTime iso={person.last_login_at} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <AddPersonDialog open={adding} onOpenChange={setAdding} />
    </div>
  );
}
