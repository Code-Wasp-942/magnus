// front_end/src/components/services/service-drawer.tsx
"use client";

import { Server, RefreshCw } from "lucide-react";

import { Drawer } from "@/components/ui/drawer";
import { Service } from "@/types/service";
import ServiceForm, { ServiceFormData } from "./service-form";


interface ServiceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialData?: Service | ServiceFormData | null;
  onSuccess: () => void;
}


export function ServiceDrawer({
  isOpen,
  onClose,
  initialData,
  onSuccess,
}: ServiceDrawerProps): JSX.Element {

  const isEdit = !!initialData;
  const title = isEdit ? "Clone / Update Service" : "Create Service";

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      icon={isEdit ? <RefreshCw className="w-5 h-5 text-blue-500" /> : <Server className="w-5 h-5 text-purple-500" />}
      width="w-[600px]"
    >
      {isOpen && (
        <ServiceForm
          initialData={initialData}
          onCancel={onClose}
          onSuccess={onSuccess}
        />
      )}
    </Drawer>
  );
}